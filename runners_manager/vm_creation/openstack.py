import logging

import keystoneauth1.session
import keystoneclient.auth.identity.v3
import neutronclient.v2_0.client
import novaclient.client
import novaclient.v2.servers
from jinja2 import FileSystemLoader, Environment

from runners_manager.runner.Runner import Runner

logger = logging.getLogger("runner_manager")

keystone_endpoint = 'https://scality.cloud/keystone/v3'


class OpenstackManager(object):
    nova_client: novaclient.client.Client
    neutron: neutronclient.v2_0.client.Client

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

    @staticmethod
    def script_init_runner(runner: Runner, token: int,
                           github_organization: str, installer: str):
        file_loader = FileSystemLoader('templates')
        env = Environment(loader=file_loader)
        env.trim_blocks = True
        env.lstrip_blocks = True
        env.rstrip_blocks = True

        template = env.get_template('init_runner_script.sh')
        output = template.render(installer=installer,
                                 github_organization=github_organization,
                                 token=token, name=runner.name, tags=','.join(runner.vm_type.tags),
                                 group='default')
        return output

    def create_vm(self, runner: Runner, runner_token: int or None,
                  github_organization: str, installer: str):
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
                                             installer)
        )

        logger.info("vm is successfully created")
        return instance

    def delete_vm(self, id):
        self.nova_client.servers.delete(id)
