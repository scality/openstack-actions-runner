import asyncio
import datetime
import logging

from runners_manager.runner.RedisManager import RedisManager
from runners_manager.runner.Runner import Runner
from runners_manager.vm_creation.CloudManager import CloudManager
from runners_manager.vm_creation.Exception import APIException
from runners_manager.vm_creation.github_actions_api import GithubManager
from runners_manager.vm_creation.VmType import VmType

logger = logging.getLogger("runner_manager")


class RunnerFactory(object):
    """
    Create / Delete / replace Runners and Virtual machine from Github and your cloud provider
    """

    github_organization: str
    runner_name_format: str
    runner_counter: int

    cloud_manager: CloudManager
    github_manager: GithubManager

    def __init__(
        self,
        cloud_manager: CloudManager,
        github_manager: GithubManager,
        organization: str,
        redis: RedisManager,
    ):
        """
        This object spawn and delete the runner and spawn the VM
        """
        self.cloud_manager = cloud_manager
        self.github_manager = github_manager
        self.github_organization = organization
        self.runner_name_format = "-{organization}-{tags}-{index}"
        self.runner_prefix = "runner-{cloud}"
        self.runner_counter = 0
        self.redis = redis

    def async_create_vm(self, runner: Runner):
        logger.info("Start creating VM")

        installer = self.github_manager.link_download_runner()
        instance = self.cloud_manager.create_vm(
            runner=runner,
            runner_token=self.github_manager.create_runner_token(),
            github_organization=self.github_organization,
            installer=installer,
        )

        if instance is None:
            logger.error(f"Creation of runner {runner} failed")
            runner.update_status("deleting")
            self.redis.delete_runner(runner)
        else:
            runner_exist = self.redis.get_runner(runner.redis_key_name())
            if runner_exist:
                runner = runner_exist
            runner.vm_id = instance.id
            self.redis.update_runner(runner)
            logger.info("Create success")

    def create_runner(self, vm_type: VmType):
        logger.info(f"Create new runner for {vm_type}")
        name = self.generate_runner_name(vm_type)
        runner = Runner(name=name, vm_id=None, vm_type=vm_type)

        try:
            asyncio.get_running_loop().run_in_executor(
                None, self.async_create_vm, runner
            )
        except RuntimeError:
            self.async_create_vm(runner)

        return runner

    def respawn_replace(self, runner: Runner):
        logger.info(f"respawn runner: {runner.name}")
        self.cloud_manager.delete_vm(runner)

        try:
            asyncio.get_running_loop().run_in_executor(
                None, self.async_create_vm, runner
            )
        except RuntimeError:
            self.async_create_vm(runner)

        runner.status_history = []
        runner.vm_id = None
        runner.created_at = datetime.datetime.now()
        return runner

    def delete_runner(self, runner: Runner):
        logger.info(f"Deleting {runner.name}: type {runner.vm_type}")
        try:
            if runner.action_id:
                self.github_manager.force_delete_runner(runner.action_id)

            if runner.vm_id:
                self.cloud_manager.delete_vm(runner)

            logger.info("Delete success")
        except APIException:
            logger.info(
                f"APIException catch, when try to delete the runner: {str(runner)}"
            )

    def generate_runner_name(self, vm_type: VmType):
        """
        Generating unused name for runner, used in Redis in Github
        :param vm_type:
        :return:
        """
        vm_type.tags.sort()
        prefix = self.runner_prefix.format(cloud=self.cloud_manager.name)
        name = self.runner_name_format.format(
            index=self.runner_counter,
            organization=self.github_organization,
            tags="-".join(vm_type.tags),
        )
        self.runner_counter += 1
        # Check that a virtual machine hasn't this name already
        if self.redis.redis.get(f"runners:{name}") is not None:
            return self.generate_runner_name(vm_type)
        return f"{prefix} {name}"
