import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import fakeredis
from runners_manager.monitoring.prometheus import metrics
from runners_manager.runner.Manager import Manager
from runners_manager.runner.RedisManager import RedisManager
from runners_manager.runner.Runner import Runner
from runners_manager.runner.RunnerManager import RunnerManager
from runners_manager.vm_creation.VmType import VmType


class ObjectId(object):
    def __init__(self, id):
        self.id = id


class TestRunnerManager(unittest.TestCase):
    factory: MagicMock

    @patch("runners_manager.vm_creation.github_actions_api.GithubManager")
    @patch("runners_manager.vm_creation.openstack.OpenstackManager")
    def setUp(self, return_github_manager, return_cloud_manager) -> None:
        self.fake_redis = RedisManager(fakeredis.FakeStrictRedis())
        self.factory = MagicMock()
        self.factory.runner_prefix = ""
        self.vm_type_normal = VmType(
            {
                "tags": ["centos7", "small"],
                "config": {
                    "flavor": "m1.small",
                    "image": "CentOS 7 (PVHVM)",
                },
                "quantity": {"min": 2, "max": 4},
            }
        )

        self.vm_type_full = VmType(
            {
                "tags": ["centos7", "small"],
                "config": {
                    "flavor": "m1.small",
                    "image": "CentOS 7 (PVHVM)",
                },
                "quantity": {"min": 4, "max": 4},
            }
        )

    def test_init_runner_manager(self):
        self.factory.create_runner.side_effect = [
            Runner("0", None, self.vm_type_normal),
            Runner("1", None, self.vm_type_normal),
        ]
        r = RunnerManager(self.vm_type_normal, self.factory, self.fake_redis)

        self.assertEqual(self.factory.create_runner.call_count, 0)
        self.assertEqual(r.runners.__len__(), 0)
        self.assertEqual(Manager.need_new_runner(r), True)

    def test_update_runner(self):
        self.factory.create_runner.side_effect = [
            Runner("0", None, self.vm_type_normal),
            Runner("1", None, self.vm_type_normal),
            Runner("2", None, self.vm_type_normal),
        ]
        r = RunnerManager(self.vm_type_normal, self.factory, self.fake_redis)
        r.create_runner()
        r.create_runner()
        self.factory.create_runner.reset_mock()
        self.factory.delete_runner.reset_mock()
        self.factory.respawn_runner.reset_mock()

        r.update_runners(
            [
                {"name": "0", "id": 0, "status": "online", "busy": False},
                {"name": "1", "id": 1, "status": "online", "busy": False},
            ]
        )
        self.assertEqual(r.runners.__len__(), 2)
        self.assertEqual(r.runners["0"].action_id, 0)
        self.assertEqual(r.runners["0"].has_run, False)
        self.assertEqual(r.runners["0"].status, "online")
        self.factory.create_runner.assert_not_called()
        self.factory.delete_runner.assert_not_called()
        self.factory.respawn_runner.assert_not_called()

        r.update_runners(
            [
                {"name": "0", "id": 0, "status": "offline", "busy": False},
                {"name": "1", "id": 1, "status": "online", "busy": False},
            ]
        )
        self.assertEqual(r.runners["0"].action_id, 0)
        self.assertEqual(r.runners["0"].has_run, True)
        self.factory.create_runner.assert_not_called()
        self.factory.delete_runner.assert_not_called()
        self.factory.respawn_runner.assert_not_called()

        r.update_runners(
            [
                {"name": "0", "id": 0, "status": "offline", "busy": False},
                {"name": "1", "id": 1, "status": "offline", "busy": False},
            ]
        )

        self.factory.create_runner.assert_not_called()
        self.factory.delete_runner.assert_not_called()
        self.factory.respawn_runner.assert_not_called()

        r.update_runners(
            [
                {"name": "0", "id": 0, "status": "offline", "busy": False},
                {"name": "1", "id": 1, "status": "online", "busy": False},
            ]
        )
        self.factory.create_runner.assert_not_called()
        self.factory.delete_runner.assert_not_called()
        self.factory.respawn_runner.assert_not_called()

    def test_need_new_runner_current_updated(self):
        self.factory.create_runner.side_effect = [
            Runner("0", None, self.vm_type_normal),
            Runner("1", None, self.vm_type_normal),
            Runner("2", None, self.vm_type_normal),
        ]
        r = RunnerManager(self.vm_type_normal, self.factory, self.fake_redis)
        r.create_runner()
        r.create_runner()

        self.assertEqual(Manager.need_new_runner(r), False)

        r.update_runner({"name": "0", "status": "online", "busy": True, "id": "0"})
        self.assertEqual(Manager.need_new_runner(r), True)

        r.runners["0"].status_history = ["online", "running"]
        r.runners["0"].status = "offline"
        self.assertEqual(Manager.need_new_runner(r), True)

        r.runners["0"].status_history = ["online", "running"]
        r.runners["0"].status = "offline"
        self.assertEqual(Manager.need_new_runner(r), True)

        r.runners["0"].status_history = ["online"]
        r.runners["0"].status = "running"
        r.runners["1"].status_history = ["online"]
        r.runners["1"].status = "running"
        self.assertEqual(Manager.need_new_runner(r), True)

    def test_need_new_runner_current_full(self):
        self.factory.create_runner.side_effect = [
            Runner("0", None, self.vm_type_full),
            Runner("1", None, self.vm_type_full),
            Runner("2", None, self.vm_type_full),
            Runner("3", None, self.vm_type_full),
        ]
        r = RunnerManager(self.vm_type_full, self.factory, self.fake_redis)
        r.create_runner()
        r.create_runner()
        r.create_runner()
        r.create_runner()
        self.assertEqual(Manager.need_new_runner(r), False)

        r.runners["0"].status_history = ["online"]
        r.runners["0"].status = "running"
        self.assertEqual(Manager.need_new_runner(r), False)

    def test_runners_syncronisation(self):
        self.factory.create_runner.side_effect = [
            Runner("0", None, self.vm_type_full),
            Runner("1", None, self.vm_type_full),
            Runner("2", None, self.vm_type_full),
            Runner("3", None, self.vm_type_full),
        ]
        r = RunnerManager(self.vm_type_full, self.factory, self.fake_redis)
        r.create_runner()
        r.create_runner()

        r2 = RunnerManager(self.vm_type_full, self.factory, self.fake_redis)
        self.assertEqual(r.redis_key_name(), "managers:centos7-small")
        self.assertEqual(r.redis_key_name(), r2.redis_key_name())
        self.assertListEqual(list(r.runners.keys()), list(r2.runners.keys()))
        self.assertEqual(r.runners["0"], r2.runners["0"])

    def test_runner_status(self):
        """Ensure runner status is updated accordingly"""
        self.factory.create_runner.side_effect = [
            Runner("0", None, self.vm_type_normal),
            Runner("1", None, self.vm_type_normal),
        ]
        r = RunnerManager(self.vm_type_normal, self.factory, self.fake_redis)

        r.create_runner()
        r.create_runner()

        self.assertEqual(r.runners["0"].status, "creating")
        self.assertEqual(r.runners["1"].status, "creating")

        # Ensure Prometheus metrics are set accordingly
        for sample in metrics.runner_status.collect()[0].samples:
            if sample.labels["openstack_actions_runner_status"] == "creating":
                self.assertEqual(sample.value, 1)

        r.update_runners(
            [
                {"name": "0", "id": 0, "status": "online", "busy": False},
                {"name": "1", "id": 1, "status": "online", "busy": True},
            ]
        )

        self.assertEqual(r.runners["0"].status, "online")
        self.assertEqual(r.runners["1"].status, "running")
        # Check if runner are running and online on Prometheus metrics
        for sample in metrics.runner_status.collect()[0].samples:
            if (
                sample.labels["name"] == "0"
                and sample.labels["openstack_actions_runner_status"] == "online"
            ):
                self.assertEqual(sample.value, 1)
            elif (
                sample.labels["name"] == "1"
                and sample.labels["openstack_actions_runner_status"] == "running"
            ):
                self.assertEqual(sample.value, 1)

        r.respawn_runner(r.runners["0"])
        self.assertEqual(r.runners["0"].status, "respawning")
        # Check if runner 0 is respawning on Prometheus metrics
        for sample in metrics.runner_status.collect()[0].samples:
            if (
                sample.labels["name"] == "0"
                and sample.labels["openstack_actions_runner_status"] == "respawning"
            ):
                self.assertEqual(sample.value, 1)

        r.delete_runner(r.runners["1"])
        self.assertNotIn("1", r.runners.keys())

    def test_runners_not_listed_on_github(self):
        self.factory.create_runner.side_effect = [
            Runner("0", None, self.vm_type_normal),
            Runner("1", None, self.vm_type_normal),
            Runner("2", None, self.vm_type_normal),
        ]
        r = RunnerManager(self.vm_type_normal, self.factory, self.fake_redis)
        r.create_runner()
        r.create_runner()
        self.factory.create_runner.reset_mock()
        self.factory.delete_runner.reset_mock()
        self.factory.respawn_runner.reset_mock()

        r.update_runners(
            [
                {"name": "0", "id": 0, "status": "online", "busy": False},
                {"name": "1", "id": 1, "status": "online", "busy": False},
            ]
        )

        r.update_runners([{"name": "0", "id": 0, "status": "online", "busy": True}])
        self.assertEqual(r.runners.__len__(), 1)
