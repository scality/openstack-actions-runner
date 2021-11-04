import unittest
import fakeredis
from unittest.mock import patch, MagicMock

from runners_manager.runner.Manager import Manager


class ObjectId(object):
    def __init__(self, id):
        self.id = id


class TestRunnerManager(unittest.TestCase):
    def setUp(self) -> None:
        self.fake_redis = fakeredis.FakeStrictRedis()
        self.github_manager = MagicMock()
        self.openstack_manager = MagicMock()

        self.github_manager.link_download_runner.return_value = 'fake_link'
        self.github_manager.create_runner_token.return_value = ''
        self.github_manager.get_runners.return_value = []
        self.github_manager.force_delete_runner.return_value = None

        self.openstack_manager.script_init_runner.return_value = ''
        self.openstack_manager.create_vm.return_value = ObjectId('str')
        self.openstack_manager.delete_vm.return_value = None

    @patch('runners_manager.runner.Manager.RunnerManager')
    @patch('runners_manager.runner.Manager.RunnerFactory')
    @patch('runners_manager.runner.Manager.redis.Redis')
    def test_no_config(self, redis, factory, manager):
        r = Manager({
            'github_organization': 'test',
            'github_repo': None,
            'runner_pool': [],
            'redis': {
                'host': 'test',
                'port': 1234
            },
            'extra_runner_timer': {
                'minutes': 10,
                'hours': 0
            },
            'timeout_runner_timer': {
                'minutes': 0,
                'hours': 1
            }}, self.openstack_manager, self.github_manager, self.fake_redis)
        self.assertEqual(r.runner_managers, [])
        self.assertEqual((r.timeout_runner_timer.seconds // 60) % 60, 0)
        self.assertEqual(r.timeout_runner_timer.seconds // 3600, 1)

        self.assertEqual((r.extra_runner_online_timer.seconds // 60) % 60, 10)
        self.assertEqual(r.extra_runner_online_timer.seconds // 3600, 0)

    @patch('runners_manager.runner.Manager.RunnerManager')
    @patch('runners_manager.runner.Manager.RunnerFactory')
    @patch('runners_manager.runner.Manager.redis.Redis')
    def test_config_vm_type(self, redis, factory, manager):
        r = Manager({'github_organization': 'test',
                     'github_repo': None,
                     'runner_pool': [{
                         'tags': ['centos7', 'small'],
                         'flavor': 'm1.small',
                         'image': 'CentOS 7 (PVHVM)',
                         'quantity': {
                             'min': 2,
                             'max': 4
                         },
                     }],
                     'redis': {
                         'host': 'test',
                         'port': 1234
                     },
                     'extra_runner_timer': {
                         'minutes': 10,
                         'hours': 10
                     },
                     'timeout_runner_timer': {
                         'minutes': 10,
                         'hours': 10
                     }}, self.openstack_manager, self.github_manager, self.fake_redis)
        self.assertEqual(r.runner_managers.__len__(), 1)

    @patch('runners_manager.runner.Manager.RunnerManager.__init__', return_value=None)
    @patch('runners_manager.runner.Manager.RunnerManager.update')
    @patch('runners_manager.runner.Manager.RunnerManager.respawn_runner')
    @patch('runners_manager.runner.Manager.RunnerManager.create_runner')
    @patch('runners_manager.runner.Manager.RunnerManager.delete_runner')
    @patch('runners_manager.runner.Manager.RunnerManager.min_runner_number', return_value=3)
    @patch('runners_manager.runner.Manager.RunnerManager.filter_runners', return_value=[])
    @patch('runners_manager.runner.Manager.Manager.need_new_runner', return_value=False)
    @patch('runners_manager.runner.Manager.Manager.log_runners_infos')
    @patch('runners_manager.runner.Manager.RunnerFactory')
    def test_update_without_changes(self, *args, **kwargs):
        r = Manager({'github_organization': 'test',
                     'github_repo': None,
                     'runner_pool': [{
                         'tags': ['centos7', 'small'],
                         'flavor': 'm1.small',
                         'image': 'CentOS 7 (PVHVM)',
                         'quantity': {
                             'min': 2,
                             'max': 4
                         },
                     }],
                     'redis': {
                         'host': 'test',
                         'port': 1234
                     },
                     'extra_runner_timer': {
                         'minutes': 10,
                         'hours': 10
                     },
                     'timeout_runner_timer': {
                         'minutes': 10,
                         'hours': 10
                     }}, self.openstack_manager, self.github_manager, self.fake_redis)
        r.update([{'id': 1, 'name': '1',
                   'os': 'linux', 'status': 'online',
                   'busy': False,
                   'labels': [{'id': 77, 'name': 'self-hosted', 'type': 'read-only'}]},
                  {'id': 2, 'name': '2',
                   'os': 'linux', 'status': 'online', 'busy': False,
                   'labels': [{'id': 77, 'name': 'self-hosted', 'type': 'read-only'}]}])
        self.assertEqual(r.runner_managers[0].update.call_count, 1)
        self.assertEqual(r.runner_managers[0].filter_runners.call_count, 3)
        self.assertEqual(r.runner_managers[0].respawn_runner.call_count, 0)
        self.assertEqual(r.runner_managers[0].create_runner.call_count, 0)
        self.assertEqual(r.runner_managers[0].respawn_runner.call_count, 0)
        self.assertEqual(r.runner_managers[0].delete_runner.call_count, 0)
