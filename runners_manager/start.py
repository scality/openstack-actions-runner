import argparse
import os

from runners_manager.settings.yaml_config import setup_settings
from runners_manager.main import main


def setup_parser():
    parser = argparse.ArgumentParser(add_help=True,
                                     description='Start and manage github self-host runners')

    parser.add_argument(
        '--settings-file',
        default='setting.yaml',
        help="Path to project settings file")
    parser.add_argument(
        '--github-token',
        default=os.getenv('GITHUB_TOKEN'),
        help="Token for github API calls",
    )
    parser.add_argument(
        '--cloud-nine-user',
        default=os.getenv('CLOUD_NINE_USER'),
        help="User for cloud nine connection  (Goes with password)")
    parser.add_argument(
        '--cloud-nine-password',
        default=os.getenv('CLOUD_NINE_PASSWORD'),
        help="Password for cloud nine connection (Goes with user)")
    parser.add_argument(
        '--cloud-nine-token',
        default=os.getenv('CLOUD_NINE_TOKEN'),
        help="Token for cloud nine connection")
    return parser


def start():
    parser = setup_parser()
    args = parser.parse_args()
    if not(args.cloud_nine_user and args.cloud_nine_password) and not args.cloud_nine_token:
        raise argparse.ArgumentError(args.cloud_nine_token,
                                     'You should have infos for openstack / cloud nine connection')

    settings = setup_settings(args.settings_file)
    main(settings, args)


if __name__ == "__main__":
    start()
