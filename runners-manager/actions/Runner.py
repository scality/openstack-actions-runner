
class Runner(object):
    name: str
    has_run: bool
    has_child: bool

    parent_name: str or None
    action_id: int or None
    vm_id: str or None

    def __init__(self, name, vm_id, parent_name=None):
        self.name = name
        self.vm_id = vm_id
        self.parent_name = parent_name

        self.has_run = False
        self.action_id = None
        self.has_child = False

    def replace_runner_with_new_one(self):
        pass

    def __unicode__(self):
        return f"{self.name}, github id: {self.action_id}, scality.cloud: {self.vm_id}"
