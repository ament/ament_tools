# Copyright 2014 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
