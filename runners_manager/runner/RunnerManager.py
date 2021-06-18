import datetime
import logging
from collections.abc import Callable


from runners_manager.runner.Runner import Runner
from runners_manager.vm_creation.github_actions_api import GithubManager
from runners_manager.vm_creation.openstack import OpenstackManager
from runners_manager.vm_creation.Exception import APIException
from runners_manager.runner.VmType import VmType

logger = logging.getLogger("runner_manager")


class RunnerManager(object):
    runner_counter: int
    github_organization: str

    runners: dict[str, Runner]
    runner_management: list[VmType]
    runner_name_format: str
    extra_runner_online_timer: dict

    openstack_manager: OpenstackManager
    github_manager: GithubManager

    def __init__(self, settings: dict,
                 openstack_manager: OpenstackManager,
                 github_manager: GithubManager,
                 runner_name_format: str = 'runner-{organization}-{tags}-{index}'):
        self.runner_counter = 0

        self.github_organization = settings['github_organization']
        self.runner_management = [VmType(elem) for elem in settings['runner_pool']]
        self.extra_runner_online_timer = settings['extra_runner_timer']

        self.runners = {}
        self.runner_name_format = runner_name_format
        self.openstack_manager = openstack_manager
        self.github_manager = github_manager

        for t in self.runner_management:
            for index in range(0, t.quantity['min']):
                self.create_runner(t)

    def update(self, github_runners: list[dict]):
        # Update status of each runner
        for elem in github_runners:
            runner = self.runners[elem['name']]
            runner.update_status(elem)

            if runner.action_id is None:
                runner.action_id = elem['id']

        self.log_runners_infos()

        # runner logic For each type of VM
        for vm_type in self.runner_management:
            # Always Respawn Vm
            offline_runners = self.filter_runners(vm_type, lambda r: r.has_run)
            for r in offline_runners:
                self.respawn_replace(r)

            # Create if it's still not enough
            while self.need_new_runner(vm_type):
                self.create_runner(vm_type)

            # Delete if you have too many and they are not used for the last x hours / minutes
            for elem in self.filter_runners(vm_type, lambda r: r.status == 'online'):
                if elem.time_online > datetime.timedelta(**self.extra_runner_online_timer) \
                        and self.too_much_runner(vm_type):
                    self.delete_runner(elem)

    def too_much_runner(self, vm_type: VmType):
        current_online = len(
            self.filter_runners(vm_type, lambda r: r.action_id and r.status == 'online')
        )
        return current_online > vm_type.quantity['min']

    def need_new_runner(self, vm_type: VmType):
        """
        This function define if we need new runners or not.
        This logic is based on the statement: They should be always x runner waiting,
            when x is the `min` variable set in the config file
        :param vm_type: Type of runner
        :return: True if can and need a new runner
        """
        current_online_or_creating = len(
            self.filter_runners(vm_type, lambda r: not r.has_run and not r.status == 'running')
        )
        current_running = len(self.filter_runners(vm_type, lambda r: r.status == 'running'))

        return current_online_or_creating < vm_type.quantity['min'] and \
            current_running + current_online_or_creating < vm_type.quantity['max']

    def filter_runners(self, vm_type: VmType, cond: Callable[[Runner], bool] or None = None):
        if cond:
            return list(filter(
                lambda e: e.vm_type.tags == vm_type.tags and cond(e),
                self.runners.values()
            ))
        return list(filter(
            lambda e: e.vm_type.tags == vm_type.tags,
            self.runners.values()
        ))

    def create_runner(self, vm_type: VmType):
        logger.info(f"Create new runner for {vm_type}")
        name = self.generate_runner_name(vm_type)
        installer = self.github_manager.link_download_runner()
        runner = Runner(name=name, vm_id=None, vm_type=vm_type)

        vm = self.openstack_manager.create_vm(
            runner=runner,
            runner_token=self.github_manager.create_runner_token(),
            github_organization=self.github_organization,
            installer=installer
        )
        runner.vm_id = vm.id

        self.runners[name] = runner
        self.runner_counter += 1
        logger.info("Create success")

    def respawn_replace(self, runner: Runner):
        logger.info(f"respawn runner: {runner.name}")
        self.openstack_manager.delete_vm(runner.vm_id)

        runner_token = self.github_manager.create_runner_token()
        installer = self.github_manager.link_download_runner()
        vm = self.openstack_manager.create_vm(
            runner=runner,
            runner_token=runner_token,
            github_organization=self.github_organization,
            installer=installer
        )
        runner.status_history = []
        runner.vm_id = vm.id

    def delete_runner(self, runner: Runner):
        logger.info(f"Deleting {runner.name}: type {runner.vm_type}")
        try:
            if runner.action_id:
                self.github_manager.force_delete_runner(runner.action_id)

            if runner.vm_id:
                self.openstack_manager.delete_vm(runner.vm_id)

            del self.runners[runner.name]
            logger.info("Delete success")
        except APIException:
            logger.info(f'APIException catch, when try to delete the runner: {str(runner)}')

    def generate_runner_name(self, vm_type: VmType):
        vm_type.tags.sort()
        return self.runner_name_format.format(index=self.runner_counter,
                                              organization=self.github_organization,
                                              tags='-'.join(vm_type.tags))

    def log_runners_infos(self):
        for vm_type in self.runner_management:
            offline_runners = self.filter_runners(vm_type, lambda r: r.has_run)
            online_runners = self.filter_runners(vm_type, lambda r: r.status == 'online')

            logger.info("type" + str(vm_type))
            logger.debug('Online runners')
            logger.debug(','.join([f"{elem.name} {elem.status}" for elem in online_runners]))
            logger.debug('Offline runners')
            logger.debug(','.join([f"{elem.name} {elem.status}" for elem in offline_runners]))

    def __del__(self):
        """
        Here we delete the runners currently in the manager
        TODO Remove this function when we have a persistent database
        :return:
        """
        for runner in self.runners.copy().values():
            self.delete_runner(runner)
