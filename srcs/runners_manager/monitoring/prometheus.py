"""Global class to handle all Prometheus metrics."""
import os

from fastapi.requests import Request
from fastapi.responses import Response
from prometheus_client import CollectorRegistry
from prometheus_client import CONTENT_TYPE_LATEST
from prometheus_client import Enum
from prometheus_client import Gauge
from prometheus_client import generate_latest
from prometheus_client import REGISTRY
from prometheus_client.multiprocess import MultiProcessCollector


class Metrics(object):
    def __init__(self):
        self.default_labels = [
            "name",
            "cloud",
        ]

        self.runner_vm_orphan_delete = Gauge(
            "runner_manager_vm_orphan_delete",
            "Metrics displaying the number of vm not tracked deleted",
            labelnames=self.default_labels,
        )

        self.runner_github_orphan_delete = Gauge(
            "runner_manager_github_orphan_delete",
            "Metrics displaying the number of vm not tracked deleted",
            labelnames=self.default_labels,
        )

        self.runner_status = Enum(
            "runner_manager_runner_status",
            "Metrics displaying the status of a runner",
            states=[
                "creating",
                "deleting",
                "respawning",
                "online",
                "running",
                "offline",
            ],
            labelnames=self.default_labels,
        )

        self.runner_creation_failed = Gauge(
            "runner_manager_runner_creation_failed",
            "Metrics display the number runners creations failed because of VM creation errors",
            labelnames=self.default_labels,
        )

        self.runner_creation_time_seconds = Gauge(
            "runner_manager_resource_creation_time",
            "Metrics displaying the time to create the runner resource",
            labelnames=self.default_labels,
        )

        self.runner_delete_time_seconds = Gauge(
            "runner_manager_resource_delete_time",
            "Metrics displaying the time to delete the runner resource",
            labelnames=self.default_labels,
        )


def prometheus_metrics(request: Request) -> Response:
    if "prometheus_multiproc_dir" in os.environ:
        registry = CollectorRegistry()
        MultiProcessCollector(registry)
    else:
        registry = REGISTRY

    return Response(
        generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST}
    )


metrics = Metrics()
