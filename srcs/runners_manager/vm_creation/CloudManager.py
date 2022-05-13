import abc

from marshmallow import Schema
from runners_manager.runner.Runner import Runner


class CloudManager(abc.ABC):
    CONFIG_SCHEMA: Schema = Schema
    name: str
    redhat_username: str
    redhat_password: str

    def __init__(
        self,
        name: str,
        settings: dict,
        redhat_username: str,
        redhat_password: str,
        ssh_keys: str,
    ):
        if self.CONFIG_SCHEMA is None:
            raise Exception("CONFIG_SCHEMA should be set")

        self.settings = self.CONFIG_SCHEMA().load(settings)
        self.name = name
        self.ssh_keys = ssh_keys
        self.redhat_username = redhat_username
        self.redhat_password = redhat_password

    @abc.abstractmethod
    def get_all_vms(self, organization: str) -> list[Runner]:
        raise NotImplementedError

    @abc.abstractmethod
    def create_vm(
        self,
        runner: Runner,
        runner_token: int or None,
        github_organization: str,
        installer: str,
        call_number=0,
    ):
        raise NotImplementedError

    @abc.abstractmethod
    def delete_vm(self, runner: Runner):
        raise NotImplementedError

    @abc.abstractmethod
    def delete_images_from_shelved(self, name):
        raise NotImplementedError
