from ament_package import parse_package
from ament_tools.commands.helper import argparse_existing_package
import argparse
import os


def main(args):
    parser = argparse.ArgumentParser(
        description=entry_point_data['description'],
        prog='ament package_version',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'path',
        nargs='?',
        type=argparse_existing_package,
        default=os.curdir,
        help='Path to the package',
    )
    args = parser.parse_args(args)

    package = parse_package(args.path)
    print(package.version)


# meta information of the entry point
entry_point_data = dict(
    description='Output the version of a package',
    main=main,
)
