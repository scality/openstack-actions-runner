import sched
import time
import pprint
from actions.Runner import Runner
from actions.RunnerManager import RunnerManager
from vm_creation.github_actions_api import (get_runners,
                                            create_runner_token,
                                            force_delete_runner)
from vm_creation.openstack import create_vm, delete_vm

s = sched.scheduler(time.time, time.sleep)

pprint = pprint.PrettyPrinter()
WHANTED_MACHINES = {
    'centos-8': 2,
}


def remove_runner(org: str, runner_id: int, vm_id: str):
    force_delete_runner(org, runner_id)
    delete_vm(vm_id)


def create_runner(org: str, runner_counter: str):
    print(f'create runner: {runner_counter}')
    token = create_runner_token(org)
    return create_vm(name=runner_counter, runner_token=token)


def replace_finish_runner(org, runner_counter: int, parent_name: str):
    vm_id = create_runner(org, str(runner_counter))
    runner_counter += 1
    return Runner(name=str(runner_counter), vm_id=vm_id, parent_name=parent_name), runner_counter


def maintain_number_of_runner(runner_m: RunnerManager):
    while True:
        runners = get_runners(runner_m.github_organization)
        print(f"nb runners: {len(runners['runners'])}")
        print(
            f"offline: {len([e for e in runners['runners'] if e['status'] == 'offline'])}"
        )

        for elem in runners['runners']:
            runner_m.update_runner(elem)

        time.sleep(5)


def main():
    org = 'scalanga-devl'
    runner_m = RunnerManager(org)
    maintain_number_of_runner(runner_m)


if __name__ == "__main__":
    runners = get_runners('scalanga-devl')
    pprint.pprint(runners)
    for elem in runners['runners']:
        force_delete_runner('scalanga-devl', elem['id'])
    # s.enter(60, 1, main, (s,))
    # s.run()
    main()
