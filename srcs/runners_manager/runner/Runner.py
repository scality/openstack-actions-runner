import datetime
import logging
import enum

from runners_manager.runner.VmType import VmType
from runners_manager.monitoring.prometheus import metrics

logger = logging.getLogger("runner_manager")


class Runner(object):
    """
    Represent a self-hosted runner
    It should always be synchronised with Github and Openstack data
    """
    class STATUS_TYPE(enum.Enum):
        respawning = 'respawning'
        creating = 'creating'
        running = 'running'
        online = 'online'
        offline = 'offline'
        deleting = 'deleting'

    name: str
    started_at: datetime.datetime or None
    created_at: datetime.datetime
    status: STATUS_TYPE
    status_history: list[STATUS_TYPE]

    action_id: int or None
    vm_id: str or None
    vm_type: VmType

    def __init__(self, name: str, vm_id: str or None, vm_type: VmType):
        self.name = name
        self.vm_id = vm_id
        self.vm_type = vm_type

        self.created_at = datetime.datetime.now()
        self.status = Runner.STATUS_TYPE.online
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
        return f'runners:{self.name}'

    @staticmethod
    def fromJson(data: dict):
        """
        Build a Runner from json data
        :param dict:
        :return:
        """
        runner = Runner(data["name"], data["vm_id"], VmType(data["vm_type"]))

        runner.status = Runner.STATUS_TYPE[data["status"]]
        runner.status_history = [Runner.STATUS_TYPE[elem] for elem in data["status_history"]]
        runner.action_id = data["action_id"]
        runner.created_at = datetime.datetime.strptime(data["created_at"], "%Y-%m-%d %H:%M:%S.%f")

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
        fields_to_serialized = ["name", "status", "status_history", "action_id", "vm_id"]
        d = {
            "vm_type": self.vm_type.toJson(),
            "created_at": str(self.created_at)
        }
        if self.started_at:
            d["started_at"] = str(self.started_at)
        else:
            d["started_at"] = None

        for field in fields_to_serialized:
            d[field] = self.__getattribute__(field)

        return d

    def update_status(self, status: STATUS_TYPE):
        """
        Update a runner status,
        Skip if the status didn't change or the runner is respawning and still offline
        :param status:
        :return:
        """
        if self.status == status or \
                (self.status in [Runner.STATUS_TYPE.creating, Runner.STATUS_TYPE.respawning] and status == Runner.STATUS_TYPE.offline):
            return

        if self.is_offline and status in [Runner.STATUS_TYPE.online, Runner.STATUS_TYPE.running]:
            self.started_at = datetime.datetime.now()

        self.status_history.append(self.status)

        logger.info(f'Runner {self.name} updating status from {self.status.value} to {status.value}')
        self.status = status

        metrics.runner_status.labels(
            name=self.name,
            flavor=self.vm_type.flavor,
            image=self.vm_type.image
        ).state(self.status)

        if self.status == Runner.STATUS_TYPE.deleting:
            metrics.runner_status.remove(
                self.name, self.vm_type.flavor, self.vm_type.image
            )

    def update_from_github(self, github_runner: dict):
        """Take all information from github and update the runner state"""
        # Update status
        if github_runner['status'] == Runner.STATUS_TYPE.online.value and github_runner['busy'] is True:
            self.update_status(Runner.STATUS_TYPE.running)
        else:
            self.update_status(github_runner['status'])

        # Set the action id
        self.action_id = github_runner['id']

    @property
    def time_since_created(self):
        return datetime.datetime.now() - self.created_at

    @property
    def time_online(self):
        return datetime.datetime.now() - self.started_at

    @property
    def is_offline(self) -> bool:
        """Return bool regarding runner status from GitHub point of view."""
        return self.status not in ['online', 'running']

    @property
    def has_run(self) -> bool:
        return self.is_offline and \
            (Runner.STATUS_TYPE.online in self.status_history or Runner.STATUS_TYPE.running in self.status_history
             or Runner.STATUS_TYPE.creating in self.status_history or Runner.STATUS_TYPE.respawning in self.status_history)

    @property
    def is_running(self) -> bool:
        return self.status == Runner.STATUS_TYPE.running

    @property
    def is_online(self) -> bool:
        return self.status == Runner.STATUS_TYPE.running.online

    @property
    def is_creating(self) -> bool:
        return self.status in ['creating', 'respawning']
