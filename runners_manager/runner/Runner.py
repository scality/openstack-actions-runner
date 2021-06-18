import datetime
import logging

from runners_manager.runner.VmType import VmType

logger = logging.getLogger("runner_manager")


class Runner(object):
    name: str
    started_at: datetime.datetime or None
    status: str
    status_history: list[str]

    action_id: int or None
    vm_id: str or None
    vm_type: VmType

    def __init__(self, name: str, vm_id: str or None, vm_type: VmType):
        self.name = name
        self.vm_id = vm_id
        self.vm_type = vm_type

        self.status = 'offline'
        self.status_history = []
        self.action_id = None
        self.started_at = None

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __unicode__(self):
        return f"{self.name}, github id: {self.action_id}, scality.cloud: {self.vm_id}"

    def __str__(self):
        return self.__unicode__()

    def update_status(self, elem):
        if elem['status'] == 'online' and elem['busy'] is True:
            status = 'running'
        else:
            status = elem['status']

        if self.status == status:
            return

        if self.status == 'offline' and status != 'offline':
            self.started_at = datetime.datetime.now()

        self.status_history.append(self.status)
        self.status = status

    @property
    def time_online(self):
        return datetime.datetime.now() - self.started_at

    @property
    def has_run(self) -> bool:
        return self.status == 'offline' and \
            ('online' in self.status_history or 'running' in self.status_history)
