import datetime
import logging
import redis

from runners_manager.runner.Runner import Runner
from runners_manager.vm_creation.github_actions_api import GithubManager
from runners_manager.vm_creation.openstack import OpenstackManager
from runners_manager.runner.RunnerFactory import RunnerFactory
from runners_manager.runner.RunnerManager import RunnerManager
from runners_manager.runner.VmType import VmType

logger = logging.getLogger("runner_manager")


class Manager(object):
    """
    This object contain the main logic to maintain the number of needed runners
    It manage all runners for one repository
    """
    factory: RunnerFactory
    redis: redis.Redis
    runner_managers: list[RunnerManager]
    extra_runner_online_timer: datetime.timedelta
    timeout_runner_timer: datetime.timedelta

    def __init__(self, settings: dict,
                 openstack_manager: OpenstackManager,
                 github_manager: GithubManager,
                 r: redis.Redis):
        self.factory = RunnerFactory(openstack_manager,
                                     github_manager,
                                     settings['github_organization'],
                                     settings['github_repo'])
        self.redis = r
        self.runner_managers = []
        for v_type in settings['runner_pool']:
            self.runner_managers.append(RunnerManager(VmType(v_type), self.factory, self.redis))

        self.extra_runner_online_timer = datetime.timedelta(**settings['extra_runner_timer'])
        self.timeout_runner_timer = datetime.timedelta(**settings['timeout_runner_timer'])

    def update(self, github_runners: list[dict]):
        """
        Here we update runners states with github api data
        And recalculate the need to spawn or delete runners
        :param github_runners:  Github api infos about self-hosted runners
        """
        for runner_manager in self.runner_managers:
            runner_manager.update(github_runners)

        self.log_runners_infos()

        # runner logic For each type of VM
        for manager in self.runner_managers:
            # Always Respawn Vm
            offline_runners = manager.filter_runners(lambda r: r.has_run)
            for r in offline_runners:
                manager.respawn_runner(r)

            # Create if it's still not enough
            while self.need_new_runner(manager):
                manager.create_runner()

            # Respawn runner if they are offline for more then 10min after spawn
            for elem in manager.filter_runners(self.runner_should_never_spawn):
                manager.respawn_runner(elem)

            # Delete last runners if you have too many and they are not used for the last x minutes
            runners_to_delete = manager.filter_runners(
                self.too_much_runner_online
            )[manager.min_runner_number():]
            for runner in runners_to_delete:
                manager.delete_runner(runner)

    @staticmethod
    def need_new_runner(manager: RunnerManager) -> bool:
        """
        This function define if we need new runners or not.
        This logic is based on the statement: They should be always x runner waiting,
            when x is the `min` variable set in the config file
        :param manager: RunnerManager
        :return: True if can and need a new runner
        """

        current_online_or_creating = len(
            manager.filter_runners(lambda r: not r.has_run and not r.is_running)
        )
        current_running = len(manager.filter_runners(lambda r: r.is_running))

        return current_online_or_creating < manager.min_runner_number() and \
            current_running + current_online_or_creating < manager.max_runner_number()

    def too_much_runner_online(self, runner: Runner) -> bool:
        return runner.is_online and not runner.has_run \
            and runner.time_online > self.extra_runner_online_timer

    def runner_should_never_spawn(self, runner: Runner) -> bool:
        return runner.is_offline and not runner.has_run \
            and runner.time_since_created > self.timeout_runner_timer

    def log_runners_infos(self):
        for manager in self.runner_managers:
            offline_runners = manager.filter_runners(lambda r: r.has_run)
            online_runners = manager.filter_runners(lambda r: r.is_online)

            logger.info("type" + str(manager.vm_type))
            logger.debug('Online runners')
            logger.debug(','.join([f"{elem.name} {elem.status}" for elem in online_runners]))
            logger.debug('Offline runners')
            logger.debug(','.join([f"{elem.name} {elem.status}" for elem in offline_runners]))
