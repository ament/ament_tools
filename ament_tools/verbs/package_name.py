# Copyright 2014 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import sys

from ament_tools.helper import argparse_existing_package
from ament_tools.package_types import parse_package


def prepare_arguments(parser):
    parser.add_argument(
        'path',
        nargs='?',
        help='Path to the package',
    )


def main(options):
    path = os.curdir if options.path is None else options.path
    try:
        path = argparse_existing_package(path)
    except argparse.ArgumentTypeError as exc:
        sys.exit("Error: {0}".format(exc))
    package = parse_package(path)
    print(package.name)


# meta information of the entry point
entry_point_data = dict(
    verb='package_name',
    description='Output the name of a package',
    main=main,
    prepare_arguments=prepare_arguments,
)
