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

import os

from ament_tools.build_type_discovery import yield_supported_build_types
from ament_tools.helper import argparse_existing_dir
from ament_tools.topological_order import topological_order
from ament_tools.verbs.build_pkg import main as build_pkg_main

from osrf_pycommon.cli_utils.verb_pattern import call_prepare_arguments


def argument_preprocessor(args):
    """Run verb and build_type plugin preprocessors on arguments.

    The preprocessors take in raw arguments and return potentially trimmed
    arguments and extra options to be added to the argparse NameSpace object.

    :param list args: list of arguments as str's
    :returns: tuple of left over arguments and dictionary of extra options
    :raises: SystemError if underlying assumptions are not met
    """
    extras = {}

    # For each available build_type plugin, let it run the preprocessor
    for build_type in yield_supported_build_types():
        build_type_impl = build_type.load()()
        args, tmp_extras = build_type_impl.argument_preprocessor(args)
        extras.update(tmp_extras)

    return args, extras


def prepare_arguments(parser, args):
    """Add parameters to argparse for the build verb and available plugins.

    After adding the generic verb arguments, this function loads all available
    build_type plugins and then allows the plugins to add additional arguments
    to the parser in a new :py:class:`argparse.ArgumentGroup` for that
    build_type.

    :param parser: ArgumentParser object to which arguments are added
    :type parser: :py:class:`argparse.ArgumentParser`
    :param list args: list of arguments as str's
    :returns: modified version of the original parser given
    :rtype: :py:class:`argparse.ArgumentParser`
    """
    # Add verb arguments
    parser.add_argument(
        'basepath',
        nargs='?',
        type=argparse_existing_dir,
        default=os.curdir,
        help='Base path to the packages',
    )
    parser.add_argument(
        '--build-space',
        default='/tmp/ament_build_pkg/build',
        help='Path to the build space',
    )
    parser.add_argument(
        '--install-space',
        default='/tmp/ament_build_pkg/install',
        help='Path to the install space',
    )
    parser.add_argument(
        '--test',
        action='store_true',
        default=False,
        help='Enable testing of packages',
    )

    # Allow all available build_type's to provide additional arguments
    for build_type in yield_supported_build_types():
        build_type_impl = build_type.load()()
        group = parser.add_argument_group("'{0}' build_type options"
                                          .format(build_type_impl.build_type))
        call_prepare_arguments(build_type_impl.prepare_arguments, group, args)

    return parser


def main(opts):
    packages = topological_order(opts.basepath)

    print('')
    print('# Topologoical order')
    for (path, package) in packages:
        print(' - %s' % package.name)
    print('')

    for (path, package) in packages:
        pkg_path = os.path.join(opts.basepath, path)

        print('')
        print('# Building: %s' % package.name)
        print('')
        opts.path = pkg_path
        rc = build_pkg_main(opts)
        if rc:
            return rc
