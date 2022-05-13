import os
import yaml

from os.path import exists
from marshmallow import Schema, fields
from settings.exceptions import SettingsFileNotFound, IncorrectSettingsFile


class EnvSettings(object):
    def __init__(self):
        self.setting_file = os.getenv('SETTING_FILE', default='./settings.yml')
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.redhat_username = os.getenv('REDHAT_USERNAME')
        self.redhat_password = os.getenv('REDHAT_PASSWORD')
        self.redis_password = os.getenv('REDIS_PASSWORD')


class ExtraRunnerTimer(Schema):
    minutes = fields.Int()
    hours = fields.Int()


class TimeoutRunnerTimer(Schema):
    minutes = fields.Int()
    hours = fields.Int()


class RunnerQuantity(Schema):
    min = fields.Int()
    max = fields.Int()


class RunnerPool(Schema):
    tags = fields.List(fields.Str(), required=True)
    config = fields.Dict(required=True)
    quantity = fields.Nested(RunnerQuantity, required=True)


class RedisDatabase(Schema):
    host = fields.Str(required=True)
    port = fields.Str(required=True)


class Settings(Schema):
    github_organization = fields.Str(required=True)
    cloud_name = fields.Str(required=True)
    cloud_config = fields.Dict(required=True)
    allowed_ssh_keys = fields.Str(required=False, default="")
    runner_pool = fields.Nested(RunnerPool, many=True, required=True)
    python_config = fields.Str(required=True)
    extra_runner_timer = fields.Nested(ExtraRunnerTimer, required=True)
    timeout_runner_timer = fields.Nested(TimeoutRunnerTimer, required=True)
    redis = fields.Nested(RedisDatabase, required=True)


def setup_settings(settings_file: str) -> dict:
    """Load and checks settings from a yaml file.

    Args:
        - settings_file (str): path of the yaml file to load.

    Raises:
        - SettingsFileNotFound
        - IncorrectSettingsFile if the yaml syntax can't be parsed
        - MalformedSettings if one or more fields from the settings are
                            incorrect (wrong types or missing values)

    Returns:
        The settings as a deserialized yaml object.
    """
    if not exists(settings_file):
        raise SettingsFileNotFound(settings_file)

    with open(settings_file, 'r') as f:
        try:
            # read the yaml data as pure string (no conversion)
            data = yaml.load(f, Loader=yaml.BaseLoader)
        except Exception as err:
            raise IncorrectSettingsFile(settings_file) from err

    settings = Settings().load(data)
    return settings
