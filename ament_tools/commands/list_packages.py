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
        type=existing_dir,
        default=os.curdir,
        help='Base paths to recursively crawl for packages',
    )
    args = parser.parse_args(args)

    package_paths = sorted(find_package_paths(args.basepath))
    for package_path in package_paths:
        print(package_path)


def existing_dir(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError("Path '%s' does not exist" % path)
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError("Path '%s' is not a directory" % path)
    return path


# meta information of the entry point
entry_point_data = dict(
    description='List relative paths of packages',
    main=main,
)
