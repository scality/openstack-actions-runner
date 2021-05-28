import os
import datetime
import keystoneauth1.session
import keystoneclient.auth.identity.v3
import neutronclient.v2_0.client
from novaclient import client
from pprint import PrettyPrinter

from vm_creation.github_actions_api import link_download_runner

pprinter = PrettyPrinter()

keystone_endpoint = 'https://scality.cloud/keystone/v3'
token = os.getenv("CLOUD_NINE_TOKEN")
tenant_id = os.getenv("CLOUD_NINE_TENANT")

region = 'Europe'
session = keystoneauth1.session.Session(
    auth=keystoneclient.auth.identity.v3.Token(
        auth_url=keystone_endpoint,
        token=token,
        project_id=tenant_id)
)
nova_client = client.Client(version=2, session=session, region_name=region)
neutron = neutronclient.v2_0.client.Client(session=session, region_name=region)


def script_init_runner(name, token, labels, group):
    installer = link_download_runner('scalanga-devl')
    return f"""#!/bin/bash
sudo yum install -y bind-utils yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y epel-release docker-ce docker-ce-cli containerd.io
sudo systemctl start docker

sudo useradd -m  actions
sudo usermod -aG docker,root actions
sudo bash -c "echo 'actions ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers"

sudo -H -u actions bash -c 'cd /home/actions/ && mkdir actions-runner && cd actions-runner && curl -O -L {installer['download_url']} && tar xzf ./{installer['filename']}'
sudo -H -u actions bash -c 'sudo /home/actions/actions-runner/bin/installdependencies.sh'
sudo -H -u actions bash -c '/home/actions/actions-runner/config.sh --url https://github.com/scalanga-devl --token {token} --name {name} --work _work  --labels {','.join(labels)} --runnergroup {group}'
nohup sudo -H -u actions bash -c '/home/actions/actions-runner/run.sh --once 2> /home/actions/actions-runner/logs'
""" # noqa


def create_vm(name: str, runner_token: int):
    """
    Create a small vm base on  CentOS-7-x86_64-GenericCloud-latest , with my sshkey
    :param name:
    :param runner_token:
    :return:
    """
    sec_group_id = neutron.list_security_groups()['security_groups'][0]['id']
    nic = {'net-id': neutron.list_networks(name='tenantnetwork1')['networks'][0]['id']}
    print("creating virtual machine")
    print("----------------------------")
    # print(script_init_runner(name, runner_token, ['centos'], 'default'))
    # print("----------------------------")
    instance = nova_client.servers.create(
        name=name, image=nova_client.glance.find_image('CentOS 7 (PVHVM)'),
        flavor=nova_client.flavors.find(name='m1.small'), key_name='laptot',
        security_groups=[sec_group_id], nics=[nic],
        userdata=script_init_runner(name, runner_token, ['centos'], 'default'))
    print(instance.name, instance.id)
    inst_status = instance.status

    print(f"Instance: {instance.name} is in {inst_status} state ")
    print(
        f"vms were successfully created at {datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}"
    )

    return instance.id


def delete_vm(id):
    nova_client.servers.delete(id)


if __name__ == "__main__":
    create_vm('test-script', '')
