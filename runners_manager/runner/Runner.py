import datetime
import logging

from runners_manager.runner.VmType import VmType

logger = logging.getLogger("runner_manager")


class Runner(object):
    """
    Represent a self-hosted runner
    It should always be synchronised with Github and Openstack data
    """
    name: str
    started_at: datetime.datetime or None
    created_at: datetime.datetime
    status: str
    status_history: list[str]

    action_id: int or None
    vm_id: str or None
    vm_type: VmType

    def __init__(self, name: str, vm_id: str or None, vm_type: VmType):
        self.name = name
        self.vm_id = vm_id
        self.vm_type = vm_type

        self.created_at = datetime.datetime.now()
        self.status = 'offline'
        self.status_history = []
        self.action_id = None
        self.started_at = None

    def __eq__(self, other):
        return self.toJson() == other.toJson()

    def __unicode__(self):
        return f"{self.name}, github id: {self.action_id}, scality.cloud: {self.vm_id}"

    def __str__(self):
        return self.__unicode__()

    @staticmethod
    def fromJson(dict):
        """
        Build a Runner from json data
        :param dict:
        :return:
        """
        logger.info(dict)
        runner = Runner(dict["name"], dict["vm_id"], VmType(dict["vm_type"]))

        runner.status = dict["status"]
        runner.status_history = dict["status_history"]
        runner.action_id = dict["action_id"]
        runner.created_at = datetime.datetime.strptime(dict["created_at"], "%Y-%m-%d %H:%M:%S.%f")

        if dict["started_at"]:
            runner.started_at = datetime.datetime.strptime(
                dict["started_at"], "%Y-%m-%d %H:%M:%S.%f"
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

    def update_status(self, elem):
        if elem['status'] == 'online' and elem['busy'] is True:
            status = 'running'
        else:
            status = elem['status']

        if self.status == status:
            return

        if self.is_offline and status != 'offline':
            self.started_at = datetime.datetime.now()

        self.status_history.append(self.status)
        self.status = status

    @property
    def time_since_created(self):
        return datetime.datetime.now() - self.created_at

    @property
    def time_online(self):
        return datetime.datetime.now() - self.started_at

    @property
    def has_run(self) -> bool:
        return self.is_offline and \
            ('online' in self.status_history or 'running' in self.status_history)
