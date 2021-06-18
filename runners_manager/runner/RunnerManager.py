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

    openstack_manager: OpenstackManager
    github_manager: GithubManager

    def __init__(self, org: str, config: list,
                 openstack_manager: OpenstackManager,
                 github_manager: GithubManager,
                 runner_name_format: str = 'runner-{organization}-{tags}-{index}'):
        self.runner_counter = 0
        self.github_organization = org
        self.runner_management = [VmType(elem) for elem in config]
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

        # runner logic For each type of VM
        for vm_type in self.runner_management:
            current_online = len(
                self.filter_runners(vm_type, lambda r: not r.has_run and r.action_id)
            )
            offlines = self.filter_runners(vm_type, lambda r: r.has_run)

            logger.info("type" + str(vm_type))
            logger.info(f"Currently online: {current_online}")
            logger.debug('Online runners')
            logger.debug(','.join([f"{elem.name} {elem.status}"
                                   for elem in self.filter_runners(vm_type)]))
            logger.debug('Offline runners')
            logger.debug(','.join([f"{elem.name} {elem.status}" for elem in offlines]))

            # Always Respawn Vm
            for r in offlines:
                self.respawn_replace(r)

            # Create if it's still not enough
            while self.need_new_runner(vm_type):
                self.create_runner(vm_type)

            # Delete if you have to many
            # if we can't delete the runner because of Github respawn it and try the next time ?

            if current_online > 0:
                for elem in self.filter_runners(vm_type, lambda r: r.status == 'online'):
                    if datetime.datetime.now() - elem.started_at > datetime.timedelta(hours=2):
                        self.delete_runner(elem)

    def need_new_runner(self, vm_type: VmType):
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
        runner = Runner(name=name, vm_id=None, volume_id=None, vm_type=vm_type)

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
        if runner.has_child:
            return

        logger.info(f"respawn runner: {runner.name}")
        self.openstack_manager.delete_vm(runner.vm_id)

        installer = self.github_manager.link_download_runner()
        vm = self.openstack_manager.create_vm(
            runner=runner,
            runner_token=self.github_manager.create_runner_token(),
            github_organization=self.github_organization,
            installer=installer
        )
        runner.status_history = []
        runner.vm_id = vm.id

    def respawn_volume(self, runner: Runner):
        if runner.has_child:
            return

        logger.info(f"respawn runner: {runner.name}")
        self.openstack_manager.detach_volume_from_instance(runner.vm_id)
        self.openstack_manager.delete_vm(runner.vm_id)

        installer = self.github_manager.link_download_runner()
        vm, volume = self.openstack_manager.create_vm_volume(
            runner=runner,
            runner_token=None,
            github_organization=self.github_organization,
            installer=installer
        )
        runner.status_history = []
        runner.vm_id = vm.id
        runner.volume_id = volume.id

    def delete_runner(self, runner: Runner):
        logger.info(f"Deleting {runner.name}: type {runner.vm_type}")
        try:
            if runner.action_id:
                self.github_manager.force_delete_runner(runner.action_id)
                runner.action_id = None

            if runner.vm_id:
                self.openstack_manager.delete_vm(runner.vm_id)
                runner.vm_id = None

            if runner.volume_id:
                self.openstack_manager.delete_vm_volume(runner.vm_id)
                runner.volume_id = None

            del self.runners[runner.name]
            logger.info("Delete success")
        except APIException:
            logger.info(f'APIException catch, when try to delete the runner: {str(runner)}')

    def generate_runner_name(self, vm_type: VmType):
        vm_type.tags.sort()
        return self.runner_name_format.format(index=self.runner_counter,
                                              organization=self.github_organization,
                                              tags='-'.join(vm_type.tags))

    def __del__(self):
        pass
