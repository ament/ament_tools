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
        help='Print the names of the packages but not the path',
    )
    parser.add_argument(
        '--paths-only',
        action='store_true',
        default=False,
        help='Print the paths of the packages but not the name',
    )
    parser.add_argument(
        '--depends-on',
        help='Only show packages which depend on the given package',
    )
    return parser


def get_unique_depend_names(package):
    names = {
        d.name for d in
        package.build_depends +
        package.buildtool_depends +
        package.build_export_depends +
        package.buildtool_export_depends +
        package.exec_depends +
        package.test_depends +
        package.doc_depends
        if d.evaluated_condition
    }
    for g in package.group_depends:
        if g.evaluated_condition:
            names |= set(g.members)
    return names


def main(options):
    lines = []
    if not options.topological_order:
        package_paths = find_package_paths(options.basepath)
        # parse package manifests
        packages = {}
        for package_path in package_paths:
            package_abs_path = os.path.join(options.basepath, package_path)
            package = parse_package(package_abs_path)
            packages[package_path] = package
        # evaluate conditions
        for package in packages.values():
            package.evaluate_conditions(os.environ)
        # expand group dependencies
        for package in packages.values():
            for group in package.group_depends:
                if group.evaluated_condition:
                    group.extract_group_members(packages.values())
        for package_path, package in packages.items():
            if options.depends_on is not None:
                if options.depends_on not in get_unique_depend_names(package):
                    continue
            if options.names_only:
                lines.append(package.name)
            elif options.paths_only:
                lines.append(package_path)
            else:
                lines.append(package.name + ' ' + package_path)
        lines.sort()
    else:
        packages = find_unique_packages(options.basepath)
        packages = topological_order_packages(packages)
        for package_path, package, _ in packages:
            if options.depends_on is not None:
                if options.depends_on not in get_unique_depend_names(package):
                    continue
            if options.names_only:
                lines.append(package.name)
            elif options.paths_only:
                lines.append(package_path)
            else:
                lines.append(package.name + ' ' + package_path)
    for line in lines:
        print(line)


# meta information of the entry point
entry_point_data = {
    'verb': 'list_packages',
    'description': 'List names and relative paths of packages',
    # Called for execution, given parsed arguments object
    'main': main,
    # Called first to setup argparse, given argparse parser
    'prepare_arguments': prepare_arguments,
}
