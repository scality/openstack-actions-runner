from marshmallow import Schema, fields
from runners_manager.runner.Runner import Runner
from runners_manager.vm_creation.VmType import DefaultVmConfig, VmType


class OpenstackConfig(Schema):
    endpoint = fields.Str(required=True)
    region = fields.Str(required=True)
    project_name = fields.Str(required=True)
    network_name = fields.Str(required=True)

    username = fields.Str(required=False)
    password = fields.Str(required=False)
    token = fields.Str(required=False)


OpenstackVmConfig = DefaultVmConfig


class OpenstackVmType(VmType):
    CONFIG_SCHEMA: OpenstackVmConfig = OpenstackVmConfig


class OpenstackRunner(Runner):
    vm_type: OpenstackVmType or None
