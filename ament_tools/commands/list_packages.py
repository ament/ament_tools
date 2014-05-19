from ament_tools.commands.helper import argparse_existing_dir
from ament_tools.packages import find_package_paths
import argparse
import os


def main(args):
    parser = argparse.ArgumentParser(
        description=entry_point_data['description'],
        prog='ament list_packages',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'basepath',
        nargs='?',
        type=argparse_existing_dir,
        default=os.curdir,
        help='Base paths to recursively crawl for packages',
    )
    args = parser.parse_args(args)

    package_paths = sorted(find_package_paths(args.basepath))
    for package_path in package_paths:
        print(package_path)


# meta information of the entry point
entry_point_data = dict(
    description='List relative paths of packages',
    main=main,
)
