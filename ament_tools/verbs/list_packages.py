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

import os

from ament_tools.helper import argparse_existing_dir
from ament_tools.package_types import parse_package
from ament_tools.packages import find_package_paths
from ament_tools.packages import find_unique_packages
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
        '--topological-order', '-t',
        action='store_true',
        default=False,
        help='Order output based on topological order',
    )
    parser.add_argument(
        '--names-only',
        action='store_true',
        default=False,
        help='Print the name of the packages not the path',
    )
    parser.add_argument(
        '--depends-on',
        help='Only show packages which depend on the given package'
    )
    return parser


def get_unique_depend_names(package):
    return list(set(
        [d.name for d in
         package.build_depends +
         package.buildtool_depends +
         package.build_export_depends +
         package.buildtool_export_depends +
         package.exec_depends +
         package.test_depends +
         package.doc_depends]
    ))


def main(options):
    if not options.topological_order:
        package_paths = find_package_paths(options.basepath)
        for package_path in sorted(package_paths):
            package = None
            package_abs_path = os.path.join(options.basepath, package_path)
            if options.depends_on is not None:
                package = parse_package(package_abs_path)
                if options.depends_on not in get_unique_depend_names(package):
                    continue
            if options.names_only:
                package = package or parse_package(package_abs_path)
                print(package.name)
            else:
                print(package_path)
    else:
        packages = find_unique_packages(options.basepath)
        packages = topological_order_packages(packages)
        for package_path, package, _ in packages:
            if options.depends_on is not None:
                if options.depends_on not in get_unique_depend_names(package):
                    continue
            if options.names_only:
                print(package.name)
            else:
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
