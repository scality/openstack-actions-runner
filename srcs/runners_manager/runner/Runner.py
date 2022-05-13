import datetime
import logging

from runners_manager.monitoring.prometheus import metrics
from runners_manager.vm_creation.VmType import VmType

logger = logging.getLogger("runner_manager")


class Runner(object):
    """
    Represent a self-hosted runner
    It should always be synchronised with Github and your Cloud provider data
    """

    name: str
    started_at: datetime.datetime or None
    created_at: datetime.datetime
    status: str
    status_history: list[str]

    action_id: int or None
    vm_id: str or None
    vm_type: VmType or None

    def __init__(self, name: str, vm_id: str or None, vm_type: VmType or None):
        self.name = name
        self.vm_id = vm_id
        self.vm_type = vm_type

        self.created_at = datetime.datetime.now()
        self.status = "offline"
        self.status_history = []
        self.action_id = None
        self.started_at = None

    def __eq__(self, other):
        return self.toJson() == other.toJson()

    def __unicode__(self):
        return f"{self.name}, github id: {self.action_id}, scality.cloud: {self.vm_id}"

    def __str__(self):
        return self.__unicode__()

    def redis_key_name(self):
        """
        Define the redis key name for this instance
        :return:
        """
        return f"runners:{self.name}"

    @staticmethod
    def fromJson(data: dict):
        """
        Build a Runner from json data
        :param dict:
        :return:
        """
        runner = Runner(data["name"], data["vm_id"], VmType(data["vm_type"]))

        runner.status = data["status"]
        runner.status_history = data["status_history"]
        runner.action_id = data["action_id"]
        runner.created_at = datetime.datetime.strptime(
            data["created_at"], "%Y-%m-%d %H:%M:%S.%f"
        )

        if data["started_at"]:
            runner.started_at = datetime.datetime.strptime(
                data["started_at"], "%Y-%m-%d %H:%M:%S.%f"
            )
        else:
            runner.started_at = None
        return runner

    def toJson(self):
        """
        The fields_to_serialized, list the field to put in the dict
        :return: dict object representative of Self
        """
        fields_to_serialized = [
            "name",
            "status",
            "status_history",
            "action_id",
            "vm_id",
        ]
        d = {"vm_type": self.vm_type.toJson(), "created_at": str(self.created_at)}
        if self.started_at:
            d["started_at"] = str(self.started_at)
        else:
            d["started_at"] = None

        for field in fields_to_serialized:
            d[field] = self.__getattribute__(field)

        return d

    def update_status(self, status: str):
        """
        Update a runner status,
        Skip if the status didn't change or the runner is respawning and still offline
        :param status:
        :return:
        """
        if self.status == status or (
            self.status in ["creating", "respawning"] and status == "offline"
        ):
            return

        if self.is_offline and status in ["online", "running"]:
            self.started_at = datetime.datetime.now()

        self.status_history.append(self.status)

        logger.info(
            f"Runner {self.name} updating status from {self.status} to {status}"
        )
        self.status = status

        metrics.runner_status.labels(
            name=self.name
        ).state(self.status)

        if self.status == "deleting":
            metrics.runner_status.remove(
                self.name
            )

    def update_from_github(self, github_runner: dict):
        """Take all information from github and update the runner state"""
        # Update status
        if github_runner["status"] == "online" and github_runner["busy"] is True:
            self.update_status("running")
        else:
            self.update_status(github_runner["status"])

        # Set the action id
        self.action_id = github_runner["id"]

    @property
    def time_since_created(self):
        return datetime.datetime.now() - self.created_at

    @property
    def time_online(self):
        return datetime.datetime.now() - self.started_at

    @property
    def is_offline(self) -> bool:
        """Return bool regarding runner status from GitHub point of view."""
        return self.status not in ["online", "running"]

    @property
    def has_run(self) -> bool:
        return self.is_offline and (
            "online" in self.status_history
            or "running" in self.status_history
            or "creating" in self.status_history
            or "respawning" in self.status_history
        )

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @property
    def is_online(self) -> bool:
        return self.status == "online"

    @property
    def is_creating(self) -> bool:
        return self.status in ["creating", "respawning"]
