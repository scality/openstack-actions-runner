import logging
import time

import keystoneauth1.session
import keystoneclient.auth.identity.v3
import neutronclient.v2_0.client
import cinderclient.client
import novaclient.client
import novaclient.v2.servers
from jinja2 import FileSystemLoader, Environment

from runners_manager.runner.Runner import Runner

logger = logging.getLogger("runner_manager")

keystone_endpoint = 'https://scality.cloud/keystone/v3'


class OpenstackManager(object):
    nova_client: novaclient.client.Client
    neutron: neutronclient.v2_0.client.Client
    cinder_client: cinderclient.client

    def __init__(self, project_name, token, username, password, region):
        if username and password:
            logger.info("Openstack auth with basic credentials")
            session = keystoneauth1.session.Session(
                auth=keystoneclient.auth.identity.v3.Password(
                    auth_url=keystone_endpoint,
                    username=username,
                    password=password,
                    user_domain_name='default',
                    project_name=project_name,
                    project_domain_id='default')
            )
        else:
            logger.info("Openstack auth with token")
            session = keystoneauth1.session.Session(
                auth=keystoneclient.auth.identity.v3.Token(
                    auth_url=keystone_endpoint,
                    token=token,
                    project_name=project_name,
                    project_domain_id='default')
            )

        self.nova_client = novaclient.client.Client(version=2, session=session, region_name=region)
        self.neutron = neutronclient.v2_0.client.Client(session=session, region_name=region)
        self.cinder_client = cinderclient.client.Client('3', session=session, region_name=region)

    @staticmethod
    def script_init_runner(runner: Runner, token: int,
                           github_organization: str, installer: str, need_new_volume: bool,
                           template_name='init_runner_script_replace.sh'):
        file_loader = FileSystemLoader('templates')
        env = Environment(loader=file_loader)
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.rstrip_blocks = True

        template = env.get_template(template_name)
        output = template.render(installer=installer, create_volume=need_new_volume,
                                 github_organization=github_organization,
                                 token=token, name=runner.name, tags=','.join(runner.vm_type.tags),
                                 group='default')
        return output

    def volume_logic(self, instance: novaclient.v2.servers.Server,
                     volume_id: str or None, mount_point='/dev/vdb'):
        if volume_id is None:
            volume = self.cinder_client.volumes.create(
                name=instance.name,
                description='volume for runner manager',
                volume_type="SATA",
                size=5
            )
            volume_id = volume.id

        else:
            volume = self.cinder_client.volumes.get(volume_id)

        while self.cinder_client.volumes.get(volume.id).status != "available":
            logger.debug(f"wait available {self.cinder_client.volumes.get(volume.id).status}")
            time.sleep(2)

        self.cinder_client.volumes.attach(volume.id, instance.id, mount_point, mode='rw')
        self.nova_client.volumes.create_server_volume(instance.id, volume.id, mount_point)
        while self.cinder_client.volumes.get(volume.id).status != "in-use":
            logger.debug(f"wait in use {self.cinder_client.volumes.get(volume.id).status}")
            time.sleep(2)

        return volume_id

    def create_vm(self, runner: Runner, runner_token: int or None,
                  github_organization: str, installer: str, need_new_volume=False):
        """
        TODO `tenantnetwork1` is a hardcoded network we should put this in config later on
        """

        sec_group_id = self.neutron.list_security_groups()['security_groups'][0]['id']
        nic = {'net-id': self.neutron.list_networks(name='tenantnetwork1')['networks'][0]['id']}
        instance = self.nova_client.servers.create(
            name=runner.name, image=self.nova_client.glance.find_image(runner.vm_type.image),
            flavor=self.nova_client.flavors.find(name=runner.vm_type.flavor),
            security_groups=[sec_group_id], nics=[nic],
            userdata=self.script_init_runner(runner, runner_token, github_organization,
                                             installer, need_new_volume,
                                             'init_runner_script_replace.sh')
        )

        logger.info("vm is successfully created")
        return instance

    def create_vm_volume(self, runner: Runner, runner_token: int or None,
                         github_organization: str, installer: str):
        """
        Create a new VM with the parameters in VmType
        TODO `tenantnetwork1` is a hardcoded network we should put this in config later on
        """
        logger.info("creating virtual machine")
        need_new_volume = runner.volume_id is None

        sec_group_id = self.neutron.list_security_groups()['security_groups'][0]['id']
        nic = {'net-id': self.neutron.list_networks(name='tenantnetwork1')['networks'][0]['id']}
        instance = self.nova_client.servers.create(
            name=runner.name, image=self.nova_client.glance.find_image(runner.vm_type.image),
            flavor=self.nova_client.flavors.find(name=runner.vm_type.flavor),
            security_groups=[sec_group_id], nics=[nic],
            userdata=self.script_init_runner(runner, runner_token,
                                             github_organization, installer, need_new_volume,
                                             'init_runner_script_replace.sh'))
        while instance.status != 'ACTIVE':
            instance = self.nova_client.servers.get(instance.id)

        logger.info("vm is successfully created")
        volume = self.volume_logic(instance, runner.volume_id)

        return instance, volume

    def detach_volume_from_instance(self, id):
        for elem in self.cinder_client.volumes.list():
            if elem.attachments and elem.attachments[0]['server_id'] == id:
                logger.info(f"try detach volume from server :{id}")
                for e in elem.attachments:
                    self.cinder_client.volumes.detach(elem, e['attachment_id'])
                    self.nova_client.volumes.delete_server_volume(id, volume_id=elem.id)

            while self.cinder_client.volumes.get(elem.id).status != "available":
                time.sleep(2)

            logger.info(f"volume {elem.id} is detach from vm {id}")

    def delete_vm_volume(self, id):
        self.detach_volume_from_instance(id)
        for elem in self.cinder_client.volumes.list():
            if elem.attachments and elem.attachments[0]['server_id'] == id:
                self.cinder_client.volumes.delete(elem.id)

    def delete_vm(self, id):
        self.nova_client.servers.delete(id)
