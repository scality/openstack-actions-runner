#!/usr/bin/env bash
sudo groupadd docker
sudo useradd -m  actions
sudo usermod -aG docker,root actions
sudo bash -c "echo 'actions ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers"

while [ ! -b /dev/vdb ]
do
  echo "/dev/vdb does not exist"
  sleep 2 # or less like 0.2
done
sleep 30
echo "vdb exist"

{% if create_volume %}
sudo parted -s -a optimal -- /dev/vdb mklabel gpt
sudo parted -s -a optimal -- /dev/vdb mkpart primary 0% 100%
sudo parted -s -- /dev/vdb align-check optimal 1
sudo mkfs.xfs /dev/vdb1
sudo -H -u actions bash -c 'mkdir -p /home/actions/actions-runner'
sudo -H -u actions bash -c 'echo "/dev/vdb1 /home/actions/actions-runner xfs defaults 0 0" | sudo tee -a /etc/fstab'
{% endif %}

sudo -H -u actions bash -c 'mkdir -p /home/actions/actions-runner'
sudo -H -u actions bash -c 'sudo mount /dev/vdb1 /home/actions/actions-runner'
sudo chown -R actions:actions /home/actions/actions-runner
sudo -H -u actions bash -c 'cd /home/actions/actions-runner && curl -O -L {{ installer["download_url"] }} && tar xzf ./{{ installer["filename"] }}'
sudo -H -u actions bash -c 'sudo /home/actions/actions-runner/bin/installdependencies.sh'

{% if token is not none %}
sudo -H -u actions bash -c '/home/actions/actions-runner/config.sh --url https://github.com/{{ github_organization }} --token {{ token }} --name "{{ name }}" --work _work  --labels {{ tags }} --runnergroup {{ group }} --replace'
{% else %}
echo "no connection token"
{% endif %}

nohup sudo -H -u actions bash -c '/home/actions/actions-runner/run.sh --once 2> /home/actions/actions-runner/logs && sudo umount /dev/vdb1'
