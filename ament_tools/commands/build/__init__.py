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

from __future__ import print_function

import argparse
import os

from ament_tools.commands.build_pkg import main as build_pkg_main
from ament_tools.commands.helper import argparse_existing_dir
from ament_tools.topological_order import topological_order


def main(args):
    parser = argparse.ArgumentParser(
        description=entry_point_data['description'],
        prog='ament build',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'basepath',
        nargs='?',
        type=argparse_existing_dir,
        default=os.curdir,
        help='Base path to the packages',
    )
    parser.add_argument(
        '--build-prefix',
        default='/tmp/ament_build_pkg/build',
        help='Path to the build prefix',
    )
    parser.add_argument(
        '--install-prefix',
        default='/tmp/ament_build_pkg/install',
        help='Path to the install prefix',
    )
    ns, unknown_args = parser.parse_known_args(args)

    packages = topological_order(ns.basepath)

    print('')
    print('# Topologoical order')
    for (path, package) in packages:
        print(' - %s' % package.name)
    print('')

    for (path, package) in packages:
        pkg_path = os.path.join(ns.basepath, path)

        print('')
        print('# Building: %s' % package.name)
        print('')
        rc = build_pkg_main([
            pkg_path,
            '--build-prefix', os.path.join(ns.build_prefix, package.name),
            '--install-prefix', ns.install_prefix,
            ] +
            unknown_args)
        if rc:
            return rc


# meta information of the entry point
entry_point_data = dict(
    description='Build a set of packages',
    main=main,
)
