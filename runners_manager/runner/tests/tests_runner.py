import unittest
from unittest.mock import patch, Mock, MagicMock

from runners_manager.runner.RunnerManager import RunnerManager
from runners_manager.runner.Runner import Runner
from runners_manager.runner.VmType import VmType


class ObjectId(object):
    def __init__(self, id):
        self.id = id


class TestRunnerManager(unittest.TestCase):
    @patch('runners_manager.vm_creation.github_actions_api.GithubManager')
    @patch('runners_manager.vm_creation.openstack.OpenstackManager')
    def setUp(self, return_github_manager, return_openstack_manager) -> None:
        self.github_manager = MagicMock()
        self.github_manager.link_download_runner.return_value = 'fake_link'
        self.github_manager.create_runner_token.return_value = ''
        self.github_manager.get_runners.return_value = []
        self.github_manager.force_delete_runner.return_value = None

        self.openstack_manager = MagicMock()
        self.openstack_manager.script_init_runner.return_value = ''
        self.openstack_manager.create_vm.return_value = ObjectId('str')
        self.openstack_manager.delete_vm.return_value = None

        return_github_manager.return_value = self.github_manager
        return_openstack_manager.return_value = self.openstack_manager

    def test_initialisation_runner_manager(self):
        pass

    @patch('runners_manager.runner.RunnerManager.RunnerManager.create_runner')
    @patch('runners_manager.runner.RunnerManager.RunnerManager.delete_runner')
    def test_no_config(self, delete_runner: Mock, create_vm: Mock):
        r = RunnerManager({
            'github_organization': 'test', 'runner_pool': [],
            'extra_runner_timer': {
                'minutes': 10,
                'hours': 10
            }}, self.openstack_manager, self.github_manager)
        self.assertEqual(r.runner_counter, 0)
        self.assertEqual(r.github_organization, 'test')
        self.assertEqual(r.runner_management, [])
        self.assertEqual(r.runners, {})

        create_vm.assert_not_called()

    @patch('runners_manager.runner.RunnerManager.RunnerManager.create_runner')
    @patch('runners_manager.runner.RunnerManager.RunnerManager.delete_runner')
    def test_runner_naming_generator(self, delete_runner: Mock, create_vm: Mock):
        vm_type_centos = VmType({'tags': ['small_tag', 'centos_tag'], 'flavor': 'small',
                                 'image': 'centos', 'quantity': 1})
        vm_type_ubuntu = VmType({'tags': ['medium_tag', 'ubuntu_tag'], 'flavor': 'medium',
                                 'image': 'ubuntu', 'quantity': 1})
        r = RunnerManager({
            'github_organization': 'test', 'runner_pool': [],
            'extra_runner_timer': {
                'minutes': 10,
                'hours': 10
            }
        }, self.openstack_manager, self.github_manager)
        r.runner_counter = 1
        g = r.generate_runner_name(vm_type_centos)
        self.assertEqual(g, 'runner-test-centos_tag-small_tag-1')

        r.runner_counter += 1
        g = r.generate_runner_name(vm_type_ubuntu)
        self.assertEqual(g, 'runner-test-medium_tag-ubuntu_tag-2')

    @patch('runners_manager.runner.RunnerManager.RunnerManager.delete_runner')
    @patch('runners_manager.runner.RunnerManager.RunnerManager.generate_runner_name')
    def test_config_vm_type(self, name_generator: Mock,
                            delete_runner: Mock):
        name_generator.side_effect = ['0', '1', '2', '3']
        self.openstack_manager.create_vm.side_effect = [ObjectId('1'), ObjectId('2'), ObjectId('3')]
        r = RunnerManager({'github_organization': 'test',
                           'runner_pool': [{
                               'tags': ['centos7', 'small'],
                               'flavor': 'm1.small',
                               'image': 'CentOS 7 (PVHVM)',
                               'quantity': {
                                   'min': 2,
                                   'max': 4
                               },
                           }],
                           'extra_runner_timer': {
                               'minutes': 10,
                               'hours': 10
                           }}, self.openstack_manager, self.github_manager)
        self.assertEqual(r.github_organization, 'test')

        self.assertEqual(r.runner_management.__len__(), 1)

        self.assertEqual(r.runners.__len__(), 2)
        self.assertEqual(r.runners['0'], Runner('0', '1', r.runner_management[0]))
        self.assertEqual(r.runners['1'].__dict__,
                         Runner('1', '2', r.runner_management[0]).__dict__)
        self.assertEqual(r.runner_counter, 2)
        self.github_manager.create_runner_token.assert_called()
        self.openstack_manager.create_vm.assert_called()

    @patch('runners_manager.runner.RunnerManager.RunnerManager.delete_runner')
    @patch('runners_manager.runner.RunnerManager.RunnerManager.generate_runner_name')
    def test_update_runner(self, name_generator: Mock, delete_mock):
        name_generator.side_effect = ['0', '1', '2']
        self.openstack_manager.create_vm.side_effect = [ObjectId('1'), ObjectId('2'), ObjectId('3')]
        r = RunnerManager({
            'github_organization': 'test', 'runner_pool': [{
                'tags': ['centos7', 'small'],
                'flavor': 'm1.small',
                'image': 'CentOS 7 (PVHVM)',
                'quantity': {
                    'min': 2,
                    'max': 4
                }}],
            'extra_runner_timer': {
                'minutes': 10,
                'hours': 10
            }
        }, self.openstack_manager, self.github_manager)
        self.assertEqual(r.runner_counter, 2)
        self.assertEqual(r.github_organization, 'test')
        self.assertEqual(r.runners['0'].action_id, None)
        self.assertEqual(r.runners['0'].has_run, False)
        self.assertEqual(r.runners['0'].status, 'offline')

        self.openstack_manager.delete_vm.assert_not_called()
        self.assertEqual(self.openstack_manager.create_vm.call_count, 2)

        self.openstack_manager.create_vm.reset_mock()
        r.update([{
            'name': '0',
            'id': 0,
            'status': 'online',
            'busy': False
        }])
        self.assertEqual(r.runners['0'].action_id, 0)
        self.assertEqual(r.runners['0'].has_run, False)
        self.assertEqual(r.runners['0'].status, 'online')
        self.assertEqual(r.runner_counter, 2)

        self.openstack_manager.create_vm.assert_not_called()
        self.openstack_manager.delete_vm.assert_not_called()

        r.update([{
            'name': '0',
            'id': 0,
            'status': 'offline',
            'busy': False
        }])
        self.assertEqual(r.runners['0'].action_id, 0)
        self.assertEqual(r.runners['0'].has_run, False)
        self.openstack_manager.delete_vm.assert_called()
        self.openstack_manager.create_vm.assert_called()

        self.openstack_manager.create_vm.reset_mock()
        self.openstack_manager.delete_vm.reset_mock()

        r.update([{
            'name': '1',
            'id': 1,
            'status': 'offline',
            'busy': False
        }])
        self.openstack_manager.delete_vm.called_once()
        self.openstack_manager.create_vm.assert_not_called()

        self.openstack_manager.delete_vm.reset_mock()
        r.update([{
            'name': '1',
            'id': 1,
            'status': 'online',
            'busy': False
        }])
        self.openstack_manager.delete_vm.assert_not_called()
        self.openstack_manager.create_vm.assert_not_called()

    @patch('runners_manager.runner.RunnerManager.RunnerManager.delete_runner')
    @patch('runners_manager.runner.RunnerManager.RunnerManager.generate_runner_name')
    def test_need_new_runner_current_updated(self, mock_naming, delete_mock):
        mock_naming.side_effect = ['0', '1', '2']
        type_dict = {
            'tags': ['centos7', 'small'],
            'flavor': 'm1.small',
            'image': 'CentOS 7 (PVHVM)',
            'quantity': {
                'min': 2,
                'max': 4
            },
        }
        vm_type = VmType(type_dict)
        r = RunnerManager({'github_organization': 'test',
                           'runner_pool': [type_dict],
                           'extra_runner_timer': {
                               'minutes': 10,
                               'hours': 10
                           }}, self.openstack_manager, self.github_manager)

        self.assertEqual(r.need_new_runner(vm_type), False)

        r.runners['0'].status_history = ['online']
        r.runners['0'].status = 'running'
        self.assertEqual(r.need_new_runner(vm_type), True)

        r.runners['0'].status_history = ['online', 'running']
        r.runners['0'].status = 'offline'
        self.assertEqual(r.need_new_runner(vm_type), True)

        r.runners['0'].status_history = ['online', 'running']
        r.runners['0'].status = 'offline'
        self.assertEqual(r.need_new_runner(vm_type), True)

        r.runners['0'].status_history = ['online']
        r.runners['0'].status = 'running'
        r.runners['1'].status_history = ['online']
        r.runners['1'].status = 'running'
        self.assertEqual(r.need_new_runner(vm_type), True)

    @patch('runners_manager.runner.RunnerManager.RunnerManager.delete_runner')
    @patch('runners_manager.runner.RunnerManager.RunnerManager.generate_runner_name')
    def test_need_new_runner_current_full(self, mock_naming, delete_mock):
        mock_naming.side_effect = ['0', '1', '2', '3', '4']
        type_dict = {
            'tags': ['centos7', 'small'],
            'flavor': 'm1.small',
            'image': 'CentOS 7 (PVHVM)',
            'quantity': {
                'min': 4,
                'max': 4
            },
        }
        vm_type = VmType(type_dict)
        r = RunnerManager({
            'github_organization': 'test', 'runner_pool': [type_dict],
            'extra_runner_timer': {
                'minutes': 10,
                'hours': 10
            }
        }, self.openstack_manager, self.github_manager)
        self.assertEqual(r.need_new_runner(vm_type), False)

        r.runners['0'].status_history = ['online']
        r.runners['0'].status = 'running'
        self.assertEqual(r.need_new_runner(vm_type), False)
