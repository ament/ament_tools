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

from ament_tools.packages import find_package_paths

from ament_tools.helper import argparse_existing_dir


def prepare_arguments(parser):
    parser.add_argument(
        'basepath',
        nargs='?',
        type=argparse_existing_dir,
        default=os.curdir,
        help='Base paths to recursively crawl for packages',
    )
    return parser


def main(options):
    package_paths = sorted(find_package_paths(options.basepath))
    for package_path in package_paths:
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
