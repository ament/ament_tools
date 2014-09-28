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

import os

from ament_tools.helper import argparse_existing_dir
from ament_tools.packages import find_package_paths
from ament_tools.topological_order import find_unique_packages
from ament_tools.topological_order import topological_order_packages


def prepare_arguments(parser):
    parser.add_argument(
        'basepath',
        nargs='?',
        type=argparse_existing_dir,
        default=os.curdir,
        help='Base paths to recursively crawl for packages',
    )
    parser.add_argument(
        '--topological-order',
        action='store_true',
        default=False,
        help='Order Enable building tests',
    )
    return parser


def main(options):
    if not options.topological_order:
        package_paths = find_package_paths(options.basepath)
        for package_path in sorted(package_paths):
            print(package_path)
    else:
        packages = find_unique_packages(options.basepath)
        packages = topological_order_packages(packages)
        for package_path, _, _ in packages:
            print(package_path)

# meta information of the entry point
entry_point_data = dict(
    verb='list_packages',
    description='List relative paths of packages',
    # Called for execution, given parsed arguments object
    main=main,
    # Called first to setup argparse, given argparse parser
    prepare_arguments=prepare_arguments,
)
