"""Global class to handle all Prometheus metrics."""

import os

from prometheus_client import Enum, Gauge
from prometheus_client import (CONTENT_TYPE_LATEST, REGISTRY,
                               CollectorRegistry, generate_latest)

from prometheus_client.multiprocess import MultiProcessCollector
from fastapi.requests import Request
from fastapi.responses import Response


class Metrics(object):

    def __init__(self):
        self.common_labels = [
            'name',
        ]

        self.runner_vm_orphan_delete = Gauge(
            'openstack_actions_runner_vm_orphan_delete',
            'Metrics displaying the number of vm not tracked deleted',
        )

        self.runner_github_orphan_delete = Gauge(
            'openstack_actions_runner_github_orphan_delete',
            'Metrics displaying the number of vm not tracked deleted',
        )

        self.runner_status = Enum(
            'openstack_actions_runner_status', 'Metrics displaying the status of a runner',
            states=['creating', 'deleting', 'respawning', 'online', 'running', 'offline'],
            labelnames=self.common_labels,
        )

        self.runner_creation_failed = Gauge(
            'openstack_action_runner_creation_failed',
            'Metrics display the number runners creations failed because of VM creation errors'
        )

        self.runner_creation_time_seconds = Gauge(
            'openstack_actions_runner_resource_creation_time',
            'Metrics displaying the time to create the runner resource',
        )

        self.runner_delete_time_seconds = Gauge(
            'openstack_actions_runner_resource_delete_time',
            'Metrics displaying the time to delete the runner resource',
        )


def prometheus_metrics(request: Request) -> Response:
    if "prometheus_multiproc_dir" in os.environ:
        registry = CollectorRegistry()
        MultiProcessCollector(registry)
    else:
        registry = REGISTRY

    return Response(
        generate_latest(registry),
        headers={"Content-Type": CONTENT_TYPE_LATEST}
    )


metrics = Metrics()
