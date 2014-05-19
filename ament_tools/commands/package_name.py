from ament_package import package_exists_at
from ament_package import parse_package
from ament_package import PACKAGE_MANIFEST_FILENAME
import argparse
import os


def main(args):
    parser = argparse.ArgumentParser(
        description=entry_point_data['description'],
        prog='ament package_name',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'path',
        nargs='?',
        type=existing_dir,
        default=os.curdir,
        help='Path to the package',
    )
    args = parser.parse_args(args)

    package = parse_package(args.path)
    print(package.name)


def existing_dir(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError("Path '%s' does not exist" % path)
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError("Path '%s' is not a directory" % path)
    if not package_exists_at(path):
        raise argparse.ArgumentTypeError(
            "Path '%s' does not contain a '%s' file" %
            (path, PACKAGE_MANIFEST_FILENAME))
    return path


# meta information of the entry point
entry_point_data = dict(
    description='Output the name of a package',
    main=main,
)
