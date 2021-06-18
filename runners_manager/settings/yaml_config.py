from os.path import exists

import yaml
from marshmallow import Schema, fields
from runners_manager.settings.exceptions import SettingsFileNotFound, IncorrectSettingsFile


class ExtraRunnerTimer(Schema):
    minutes = fields.Int()
    hours = fields.Int()


class RunnerQuantity(Schema):
    min = fields.Int()
    max = fields.Int()


class RunnerPool(Schema):
    tags = fields.List(fields.Str(), required=True)
    flavor = fields.Str(required=True)
    image = fields.Str(required=True)
    quantity = fields.Nested(RunnerQuantity, required=True)


class Settings(Schema):
    github_organization = fields.Str(required=True)
    cloud_nine_region = fields.Str(required=True)
    cloud_nine_tenant = fields.Str(required=True)
    runner_pool = fields.Nested(RunnerPool, many=True, required=True)
    python_config = fields.Str(required=True)
    extra_runner_timer = fields.Nested(ExtraRunnerTimer, required=True)


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
