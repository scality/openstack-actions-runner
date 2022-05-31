import logging

from google.api_core.extended_operation import ExtendedOperation
from google.cloud.compute import AccessConfig
from google.cloud.compute import AttachedDisk
from google.cloud.compute import AttachedDiskInitializeParams
from google.cloud.compute import Image
from google.cloud.compute import ImagesClient
from google.cloud.compute import Instance
from google.cloud.compute import InstancesClient
from google.cloud.compute import Items
from google.cloud.compute import Metadata
from google.cloud.compute import NetworkInterface
from google.cloud.compute import Operation
from google.cloud.compute import ServiceAccount
from google.cloud.compute import Tags
from google.cloud.compute import ZoneOperationsClient
from runners_manager.monitoring.prometheus import metrics
from runners_manager.runner.Runner import Runner
from runners_manager.runner.Runner import VmType
from runners_manager.vm_creation.CloudManager import CloudManager
from runners_manager.vm_creation.gcloud.schema import GcloudConfig
from runners_manager.vm_creation.gcloud.schema import GcloudConfigVmType


logger = logging.getLogger("runner_manager")


class GcloudManager(CloudManager):
    CONFIG_SCHEMA = GcloudConfig
    CONFIG_VM_TYPE_SCHEMA = GcloudConfigVmType
    instances: InstancesClient = InstancesClient()
    images: ImagesClient = ImagesClient()
    operations: ZoneOperationsClient = ZoneOperationsClient()

    def __init__(
        self,
        name: str,
        settings: dict,
        redhat_username: str,
        redhat_password: str,
        ssh_keys: str,
    ):
        super(GcloudManager, self).__init__(
            name, settings, redhat_username, redhat_password, ssh_keys
        )
        self.project_id = settings.get("project_id")
        self.zone = settings.get("zone")

    def delete_existing_runner(self, runner: Runner):
        """Delete an old runner instance from gcloud if it exists."""
        for listed_runner in self.get_all_vms(runner.name):
            if runner.name == listed_runner.name:
                logger.info(f"Found an existing instance of {runner.name}")
                return self.delete_vm(listed_runner)
        logger.info(f"No existing instance for runner {runner.name} has been found")
        return None

    def configure_instance(
        self, runner, runner_token, github_organization, installer
    ) -> Instance:
        source_disk_image: Image = self.images.get_from_family(
            project=runner.vm_type.config["project"],
            family=runner.vm_type.config["family"],
        )
        machine_type = (
            f"zones/{self.zone}/machineTypes/{runner.vm_type.config['machine_type']}"
        )
        startup_script = self.script_init_runner(
            runner, runner_token, github_organization, installer
        )
        disk_size_gb = runner.vm_type.config["disk_size_gb"]
        disk_type = f"projects/{self.project_id}/zones/{self.zone}/diskTypes/pd-ssd"
        instance: Instance = Instance(
            name=runner.name,
            machine_type=machine_type,
            disks=[
                AttachedDisk(
                    boot=True,
                    auto_delete=True,
                    initialize_params=AttachedDiskInitializeParams(
                        disk_size_gb=disk_size_gb,
                        disk_type=disk_type,
                        source_image=source_disk_image.self_link,
                    ),
                )
            ],
            network_interfaces=[
                NetworkInterface(
                    network="global/networks/default",
                    access_configs=[
                        AccessConfig(type="ONE_TO_ONE_NAT", name="External NAT")
                    ],
                )
            ],
            service_accounts=[
                ServiceAccount(
                    email="default",
                    scopes=[
                        "https://www.googleapis.com/auth/devstorage.read_write",
                        "https://www.googleapis.com/auth/logging.write",
                    ],
                )
            ],
            tags=Tags(items=runner.vm_type.tags),
            metadata=Metadata(
                items=[Items(key="startup-script", value=startup_script)]
            ),
        )
        return instance

    def create_vm(
        self,
        runner: Runner,
        runner_token: int or None,
        github_organization: str,
        installer: str,
        call_number=0,
    ):
        try:
            logger.info(f"Creating {runner.name} instance")
            # self.delete_existing_runner(runner)

            instance = self.configure_instance(
                runner, runner_token, github_organization, installer
            )
            ext_operation: ExtendedOperation = self.instances.insert(
                instance_resource=instance, project=self.project_id, zone=self.zone
            )
            operation: Operation = self.operations.get(
                project=self.project_id, zone=self.zone, operation=ext_operation.name
            )
            logger.info(f"{runner.name} instance has been created")

            return operation.target_id
        except Exception as e:
            metrics.runner_creation_failed.labels(
                name=runner.name, cloud=self.name
            ).inc()
            logger.error(e)
            raise e

    def delete_vm(self, runner: Runner):
        try:
            logger.info(f"Deleting instance of runner {runner.name}...")
            self.instances.delete(
                project=self.project_id, zone=self.zone, instance=runner.name
            )
            logger.info(f"Instance of runner {runner.name} has been deleted")
        except Exception as e:
            logger.info(f"Instance of runner {runner.name} {e}")
            pass

    def get_all_vms(self, prefix: str) -> list[Runner]:
        logger.info(
            f"Retrieving runner instances hosted on gcloud with prefix {prefix}"
        )
        instances = self.instances.list(
            project=self.project_id,
            zone=self.zone,
        )
        runners: list[Runner] = []
        for instance in instances:
            if instance.name.startswith(prefix):
                runners.append(
                    Runner(
                        instance.name,
                        instance.id,
                        VmType(
                            {
                                "tags": [],
                                "config": {},
                                "quantity": {},
                            }
                        ),
                        self.name,
                    )
                )
        logger.info(
            f"{len(runners)} runners with prefix {prefix} are running on gcloud"
        )
        return runners

    def delete_images_from_shelved(self, name):
        logger.info(f"nothing to do for {name}")
