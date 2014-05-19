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
