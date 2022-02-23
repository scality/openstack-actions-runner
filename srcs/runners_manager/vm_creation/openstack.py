import logging
import time
import asyncio

import keystoneauth1.session
import keystoneclient.auth.identity.v3
import neutronclient.v2_0.client
import novaclient.client
import novaclient.v2.servers
from jinja2 import FileSystemLoader, Environment

from runners_manager.runner.Runner import Runner
from runners_manager.monitoring.prometheus import metrics


logger = logging.getLogger("runner_manager")


keystone_endpoint = 'https://scality.cloud/keystone/v3'


class OpenstackManager(object):
    nova_client: novaclient.client.Client
    neutron: neutronclient.v2_0.client.Client

    redhat_username = ""
    redhat_password = ""

    def __init__(self, project_name, token, username, password, region, redhat_username,
                 redhat_password, ssh_keys):
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

        self.redhat_username = redhat_username
        self.redhat_password = redhat_password
        self.nova_client = novaclient.client.Client(version=2, session=session, region_name=region)
        self.neutron = neutronclient.v2_0.client.Client(session=session, region_name=region)
        self.ssh_keys = ssh_keys

    def script_init_runner(self, runner: Runner, token: int,
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
                                 redhat_username=self.redhat_username,
                                 redhat_password=self.redhat_password,
                                 group='default',
                                 ssh_keys=self.ssh_keys)
        return output

    def get_all_vms(self, organization: str):
        return [vm for vm in self.nova_client.servers.list(sort_keys=['created_at'])
                if vm.name.startswith(f'runner-{organization}')]

    @metrics.runner_creation_time_seconds.time()
    def create_vm(self, runner: Runner, runner_token: int or None,
                  github_organization: str, installer: str, call_number=0):
        """
        TODO `tenantnetwork1` is a hardcoded network we should put this in config later on
        Every call with nova_client looks very unstable.
        """

        if call_number > 5:
            return None

        # Delete all VMs with the same name
        vm_list = self.nova_client.servers.list(search_opts={'name': runner.name},
                                                sort_keys=['created_at'])
        for vm in vm_list:
            self.nova_client.servers.delete(vm.id)

        instance = None
        try:

            sec_group_id = self.neutron.list_security_groups()['security_groups'][0]['id']
            nic = {'net-id': self.neutron.list_networks(name='tenantnetwork1')['networks'][0]['id']}
            image = self.nova_client.glance.find_image(runner.vm_type.image)
            flavor = self.nova_client.flavors.find(name=runner.vm_type.flavor)

            instance = self.nova_client.servers.create(
                name=runner.name,
                image=image,
                flavor=flavor,
                security_groups=[sec_group_id], nics=[nic],
                userdata=self.script_init_runner(runner, runner_token, github_organization,
                                                 installer)
            )

            while instance.status not in ['ACTIVE', 'ERROR']:
                instance = self.nova_client.servers.get(instance.id)
                time.sleep(2)

            if instance.status == 'ERROR':
                logger.info('vm failed, creating a new one')
                self.delete_vm(instance.id)
                time.sleep(2)
                metrics.runner_creation_failed.inc()
                return self.create_vm(runner, runner_token, github_organization,
                                      installer, call_number + 1)
        except Exception as e:
            logger.error(f"Vm creation raised an error, {e}")

        if not instance or not instance.id:
            metrics.runner_creation_failed.inc()
            logger.error(f"""VM not found on openstack, recreating it.
VM id: {instance.id if instance else 'Vm not created'}""")
            return self.create_vm(runner, runner_token,
                                  github_organization, installer,
                                  call_number + 1)

        logger.info("vm is successfully created")
        return instance

    @metrics.runner_delete_time_seconds.time()
    def delete_vm(self, vm_id: str, image_name=None):
        try:
            asyncio.get_running_loop().run_in_executor(None,
                                                       self.async_delete_vm,
                                                       vm_id,
                                                       image_name)
        except RuntimeError:
            self.async_delete_vm(vm_id, image_name)

    def async_delete_vm(self, vm_id: str, image_name):
        try:
            if image_name and 'rhel' in image_name:
                try:
                    nb_error = 0
                    self.nova_client.servers.shelve(vm_id)
                    s = self.nova_client.servers.get(vm_id).status
                    while s not in ['SHUTOFF', 'SHELVED_OFFLOADED'] and nb_error < 5:
                        time.sleep(5)
                        try:
                            s = self.nova_client.servers.get(vm_id).status
                            logger.info(s)
                        except Exception as e:
                            nb_error += 1
                            logger.error(f'Error in VM delete {e}')

                except Exception:
                    pass

            self.nova_client.servers.delete(vm_id)
        except novaclient.exceptions.NotFound as exp:
            # If the machine was already deleted, move along
            logger.info(exp)
            pass
