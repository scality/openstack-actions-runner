#!/usr/bin/env bash
sudo groupadd docker
sudo useradd -m  actions
sudo usermod -aG docker,root actions
sudo bash -c "echo 'actions ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers"

sudo -H -u actions bash -c 'mkdir -p /home/actions/actions-runner'
sudo -H -u actions bash -c 'cd /home/actions/actions-runner && curl -O -L {{ installer["download_url"] }} && tar xzf ./{{ installer["filename"] }}'
sudo -H -u actions bash -c 'sudo /home/actions/actions-runner/bin/installdependencies.sh'
sudo -H -u actions bash -c '/home/actions/actions-runner/config.sh --url https://github.com/{{ github_organization }} --token {{ token }} --name "{{ name }}" --work _work  --labels {{ tags }} --runnergroup {{ group }} --replace --unattended'
nohup sudo -H -u actions bash -c '/home/actions/actions-runner/run.sh --once 2> /home/actions/actions-runner/logs'
