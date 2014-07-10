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
from pkg_resources import iter_entry_points
import subprocess
import sys

from ament_package import package_exists_at
from ament_package import PACKAGE_MANIFEST_FILENAME
from ament_package import parse_package

AMENT_VERB_TEST_PKG_BUILD_TYPES_ENTRY_POINT = \
    'ament.verb.test_pkg.build_types'


def main(args):
    parser = test_pkg_parser()
    ns, unknown_args = parser.parse_known_args(args)

    build_type = get_build_type(ns.path)

    entry_points = list(iter_entry_points(
        group=AMENT_VERB_TEST_PKG_BUILD_TYPES_ENTRY_POINT,
        name=build_type))
    assert len(entry_points) <= 1
    if not entry_points:
        print("The '%s' file in '%s' exports an unknown build types: %s" %
              (PACKAGE_MANIFEST_FILENAME, ns.path, build_type),
              file=sys.stderr)
        return 1
    entry_point = entry_points[0]

    return entry_point.load()(args)


def get_build_type(path):
    package = parse_package(path)

    build_type_exports = [e for e in package.exports
                          if e.tagname == 'build_type']
    if len(build_type_exports) > 1:
        print("The '%s' file in '%s' exports multiple build types" %
              (PACKAGE_MANIFEST_FILENAME, path), file=sys.stderr)

    default_build_type = 'ament_cmake'
    if not build_type_exports:
        return default_build_type

    return build_type_exports[0].get('type', default_build_type)


def test_pkg_parser(build_type=None):
    description = entry_point_data['description']
    prog = 'ament test_pkg'
    if build_type:
        description += " with build type '%s'" % build_type
        prog += '_%s' % build_type
    parser = argparse.ArgumentParser(
        description=description,
        prog=prog,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        'path',
        nargs='?',
        type=existing_package,
        default=os.curdir,
        help='Path to the package',
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
    return parser


def existing_package(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError("Path '%s' does not exist" % path)
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError("Path '%s' is not a directory" % path)
    if not package_exists_at(path):
        raise argparse.ArgumentTypeError(
            "Path '%s' does not contain a '%s' file" %
            (path, PACKAGE_MANIFEST_FILENAME))
    return path


def run_command(cmd, cwd=None):
    msg = '# Invoking: %s' % ' '.join(cmd)
    if cwd:
        msg += ' (in %s)' % cwd
    print(msg)
    return subprocess.check_call(cmd, cwd=cwd)


# meta information of the entry point
entry_point_data = dict(
    description='Test a package',
    main=main,
)
