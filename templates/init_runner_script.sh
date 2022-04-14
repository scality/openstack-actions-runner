#!/usr/bin/env bash

source /etc/os-release
LINUX_OS=${ID}
LINUX_OS_VERSION=$(echo ${VERSION_ID} | sed -E 's/^([0-9]+)\..*$/\1/')
DOCKER_SERVICE_START="yes"

sudo groupadd -f docker
sudo useradd -m  actions
sudo usermod -aG docker,root actions
sudo bash -c "echo 'actions ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers"
sudo -H -u actions bash -c 'mkdir -p /home/actions/.ssh'
{% if ssh_keys %}
sudo -H -u actions bash -c 'echo "{{ ssh_keys }}" >>  /home/actions/.ssh/authorized_keys'
{% endif %}

if [ "${LINUX_OS}" = "ubuntu" ]
then
sudo apt-get -y update
sudo DEBIAN_FRONTEND=noninteractive apt-get -y install apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
   lsb-release
elif [ "${LINUX_OS}" = "centos" ]  ||  [ "${LINUX_OS}" = "rocky" ] || [ "${LINUX_OS}" = "almalinux" ]
then
sudo yum install -y bind-utils yum-utils
elif [ "${LINUX_OS}" = "rhel" ]
then
sudo bash -c 'cat <<EOF > /etc/systemd/system/redhat_registration.service
[Unit]
Description=Redhat registration
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=true
TimeoutStartSec=300
ExecStart=/sbin/subscription-manager register --username={{ redhat_username }} --password={{ redhat_password }} --auto-attach
TimeoutStopSec=300
ExecStop=-/sbin/subscription-manager unregister

[Install]
WantedBy=multi-user.target
EOF'
sudo chmod 600 /etc/systemd/system/redhat_registration.service
sudo systemctl daemon-reload
sudo systemctl enable redhat_registration.service
sudo systemctl start redhat_registration.service
else
echo "OS not managed by the runner-manager"
exit 1
fi

{% if not "no-docker" in tags  %}
if [ "${LINUX_OS}" = "ubuntu" ]
then
sudo apt-get -y update
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update --yes --force-yes
sudo apt-get install --yes --force-yes docker-ce docker-ce-cli containerd.io
elif [ "${LINUX_OS}" = "centos" ]  ||  [ "${LINUX_OS}" = "rocky" ] || [ "${LINUX_OS}" = "almalinux" ]
then
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y epel-release docker-ce docker-ce-cli containerd.io
elif [ "${LINUX_OS}" = "rhel" ]
then
if [ "${LINUX_OS_VERSION}" = "7" ]
then
# Enable repos to install docker
sudo mkdir /etc/docker/
sudo bash -c "cat >  /etc/docker/daemon.json << EOF
{
  "dns": ["10.100.1.1", "10.100.1.2", "10.100.1.3"]
}
EOF"

sudo subscription-manager repos --enable=rhel-7-server-extras-rpms --enable=rhel-7-server-optional-rpms
sudo yum install -y docker
elif [ "${LINUX_OS_VERSION}" = "8" ]
then
sudo dnf install -y podman-docker
DOCKER_SERVICE_START="no"
else
echo "RHEL version not managed by the runner-manager"
exit 1
fi
fi

if [ "${DOCKER_SERVICE_START}" = "yes" ]
then
sudo systemctl start docker
fi
{% endif %}

sudo -H -u actions bash -c 'mkdir -p /home/actions/actions-runner'
sudo -H -u actions bash -c 'cd /home/actions/actions-runner && curl -O -L {{ installer["download_url"] }} && tar xzf ./{{ installer["filename"] }}'
sudo -H -u actions bash -c 'sudo /home/actions/actions-runner/bin/installdependencies.sh'
sudo -H -u actions bash -c 'cd /home/actions/actions-runner && 
{% raw %}
				echo "[Unit]
Description={{Description}}
After=network.target

[Service]
ExecStart=/bin/bash {{RunnerRoot}}/runsvc.sh
User={{User}}
WorkingDirectory={{RunnerRoot}}
KillMode=process
KillSignal=SIGTERM
TimeoutStopSec=5min

[Install]
{% endraw %}
WantedBy=multi-user.target" > /home/actions/actions-runner/bin/actions.runner.service.template &&
				./config.sh --url https://github.com/{{ github_organization }} --token {{ token }} --name "{{ name }}" --work _work  --labels {{ tags }} --runnergroup {{ group }} --replace --unattended --ephemeral'
if command -v systemctl; then
sudo -H -u actions bash -c 'cd /home/actions/actions-runner &&
				sudo ./svc.sh install &&
				sudo ./svc.sh start'
else
nohup sudo -H -u actions bash -c '/home/actions/actions-runner/run.sh 2> /home/actions/actions-runner/logs'
fi
