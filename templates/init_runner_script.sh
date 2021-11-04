#!/usr/bin/env bash
source /etc/os-release
LINUX_OS=${ID}

if [ "${LINUX_OS}" = "ubuntu" ]
then
sudo apt-get -y update
sudo apt-get -y install apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
   lsb-release
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update --yes --force-yes
sudo apt-get install --yes --force-yes docker-ce docker-ce-cli containerd.io
elif [ "${LINUX_OS}" = "centos" ]
then
sudo yum install -y bind-utils yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y epel-release docker-ce docker-ce-cli containerd.io
else
echo "OS not managed by the runner-manager"
exit 1
fi

sudo systemctl start docker
sudo groupadd -f docker
sudo useradd -m  actions
sudo usermod -aG docker,root actions
sudo bash -c "echo 'actions ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers"

sudo -H -u actions bash -c 'mkdir -p /home/actions/actions-runner'
sudo -H -u actions bash -c 'cd /home/actions/actions-runner && curl -O -L {{ installer["download_url"] }} && tar xzf ./{{ installer["filename"] }}'
sudo -H -u actions bash -c 'sudo /home/actions/actions-runner/bin/installdependencies.sh'
sudo -H -u actions bash -c '/home/actions/actions-runner/config.sh --url {{ github_url }} --token {{ token }} --name "{{ name }}" --work _work  --labels {{ tags }} --runnergroup {{ group }} --replace --unattended'
nohup sudo -H -u actions bash -c '/home/actions/actions-runner/run.sh --once 2> /home/actions/actions-runner/logs'
