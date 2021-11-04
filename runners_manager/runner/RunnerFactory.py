import logging
import datetime

from runners_manager.vm_creation.github_actions_api import GithubManager
from runners_manager.vm_creation.openstack import OpenstackManager
from runners_manager.runner.Runner import Runner
from runners_manager.vm_creation.Exception import APIException
from runners_manager.runner.VmType import VmType

logger = logging.getLogger("runner_manager")


class RunnerFactory(object):
    """
    Create / Delete / replace Runners and Virtual machine from Github and Openstack
    """
    github_organization: str
    github_repo: str or None
    runner_name_format: str
    runner_counter: int

    openstack_manager: OpenstackManager
    github_manager: GithubManager

    def __init__(self, openstack_manager: OpenstackManager,
                 github_manager: GithubManager,
                 organization, repo):
        """
        This object spawn and delete the runner and spawn the VM
        """
        self.openstack_manager = openstack_manager
        self.github_manager = github_manager
        self.github_organization = organization
        self.github_repo = repo
        self.runner_counter = 0

    @property
    def runner_name_format(self):
        if self.github_repo:
            return 'runner-{organization}-{repo}-{tags}-{index}'
        return 'runner-{organization}-{tags}-{index}'

    def create_runner(self, vm_type: VmType):
        logger.info(f"Create new runner for {vm_type}")
        name = self.generate_runner_name(vm_type)
        installer = self.github_manager.link_download_runner()
        runner = Runner(name=name, vm_id=None, vm_type=vm_type)

        vm = self.openstack_manager.create_vm(
            runner=runner,
            runner_token=self.github_manager.create_runner_token(),
            github_organization=self.github_organization,
            github_repo=self.github_repo,
            installer=installer
        )
        runner.vm_id = vm.id

        self.runner_counter += 1
        logger.info("Create success")
        return runner

    def respawn_replace(self, runner: Runner):
        logger.info(f"respawn runner: {runner.name}")
        self.openstack_manager.delete_vm(runner.vm_id)

        runner_token = self.github_manager.create_runner_token()
        installer = self.github_manager.link_download_runner()
        vm = self.openstack_manager.create_vm(
            runner=runner,
            runner_token=runner_token,
            github_organization=self.github_organization,
            github_repo=self.github_repo,
            installer=installer
        )
        runner.status_history = []
        runner.vm_id = vm.id
        runner.created_at = datetime.datetime.now()
        return runner

    def delete_runner(self, runner: Runner):
        logger.info(f"Deleting {runner.name}: type {runner.vm_type}")
        try:
            if runner.action_id:
                self.github_manager.force_delete_runner(runner.action_id)

            if runner.vm_id:
                self.openstack_manager.delete_vm(runner.vm_id)

            logger.info("Delete success")
        except APIException:
            logger.info(f'APIException catch, when try to delete the runner: {str(runner)}')

    def generate_runner_name(self, vm_type: VmType):
        vm_type.tags.sort()
        return self.runner_name_format.format(index=self.runner_counter,
                                              organization=self.github_organization,
                                              repo=self.github_repo,
                                              tags='-'.join(vm_type.tags))
