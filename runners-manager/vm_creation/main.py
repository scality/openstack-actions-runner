import time
from github_actions_api import list_runners, get_runners, create_runner_token
from vm_creation.openstack import create_vm

if __name__ == '__main__':
    org = 'scalanga-devl'
    get_runners(org)
    print('-----------------------------------')
    start_time = round(time.time())
    create_token = create_runner_token(org)
    vm_id = create_vm('auto-github-runner', create_token)

    runners = list_runners(org)
    while runners['runners'].__len__() == 0:
        runners = list_runners(org)
        print(runners)
        time.sleep(5)
    print(f"{time.time() - start_time}")
    # force_delete_runner(runners['runners'][0]["id"])
    # delete_vm(vm_id)
