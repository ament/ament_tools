# Copyright 2017 Open Source Robotics Foundation, Inc.
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
import sys

from ament_tools.helper import argparse_existing_dir
from ament_tools.packages import find_packages


def prepare_arguments(parser):
    parser.add_argument(
        '--basepath',
        type=argparse_existing_dir,
        default=os.curdir,
        help='Base paths to recursively crawl for packages',
    )
    parser.add_argument(
        '--build-deps',
        action='store_true',
        help='Show only build dependencies of a given package',
    )
    parser.add_argument(
        '--doc-deps',
        action='store_true',
        help='Show only dependencies to generate documentation of a given package',
    )
    parser.add_argument(
        '--run-deps',
        action='store_true',
        help='Show only dependencies needed to run a given package',
    )
    parser.add_argument(
        '--test-deps',
        action='store_true',
        help='Show only test dependencies of a given package',
    )
    parser.add_argument(
        '--group-deps',
        action='store_true',
        help='Show only group dependencies of a given package',
    )
    parser.add_argument(
        'package',
        metavar='PACKAGE',
        help='Package to process',
    )
    return parser


def main(options):
    packages = find_packages(options.basepath)
    # show all dependencies if no options are given
    if not (
        options.build_deps or options.doc_deps or options.run_deps or
        options.test_deps or options.group_deps
    ):
        options.build_deps = True
        options.doc_deps = True
        options.run_deps = True
        options.test_deps = True
        options.group_deps = True
    for (path, package) in packages.items():
        if package.name == options.package:
            deps = []
            if options.build_deps:
                deps.extend(package.build_depends + package.buildtool_depends)
            if options.doc_deps:
                deps.extend(package.doc_depends)
            if options.run_deps:
                deps.extend(
                    package.build_export_depends +
                    package.buildtool_export_depends +
                    package.exec_depends)
            if options.test_deps:
                deps.extend(package.test_depends)
            # evaluate conditions
            package.evaluate_conditions(os.environ)
            # reduce dependencies to their names
            deps = [d.name for d in deps if d.evaluated_condition]
            # extract group memberships
            if options.group_deps:
                for g in package.group_depends:
                    if not g.evaluated_condition:
                        continue
                    g.extract_group_members(packages.values())
                    deps.append(
                        '%s (group members: %s)' %
                        (g.name, ', '.join(sorted(g.members))))
            # Remove duplicate entries, sort output
            for line in sorted(set(deps)):
                print(line)
            return
    print('No package with name {!r} found'.format(options.package), file=sys.stderr)
    return -1


entry_point_data = {
    'verb': 'list_dependencies',
    'description': 'List names of dependencies of a package',
    # Called for execution, given parsed arguments object
    'main': main,
    # Called first to setup argparse, given argparse parser
    'prepare_arguments': prepare_arguments,
}
