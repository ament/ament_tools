# Copyright 2015 Open Source Robotics Foundation, Inc.
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

from ament_tools.build_type_discovery import get_class_for_build_type

from ament_tools.context import Context
from ament_tools.helper import determine_path_argument

from ament_tools.verbs.build_pkg.cli import __get_cached_package_manifest
from ament_tools.verbs.build_pkg.cli import get_build_type
from ament_tools.verbs.build_pkg.cli import handle_build_action
from ament_tools.verbs.build_pkg.cli import validate_package_path


def add_path_argument(parser):
    """Add position path argument to parser."""
    parser.add_argument(
        'path',
        nargs='?',
        default=os.curdir,
        help='Path to the package',
    )


def prepare_arguments(parser, args):
    """Add parameters to argparse for the uninstall_pkg verb.

    :param parser: ArgumentParser object to which arguments are added
    :type parser: :py:class:`argparse.ArgumentParser`
    :param list args: list of arguments as str's
    :returns: modified version of the original parser given
    :rtype: :py:class:`argparse.ArgumentParser`
    """
    # Add verb arguments
    add_path_argument(parser)
    add_arguments(parser)

    return parser


def add_arguments(parser):
    parser.add_argument(
        '--build-space',
        help="Path to the build space (default 'CWD/build')",
    )
    parser.add_argument(
        '--install-space',
        help="Path to the install space (default 'CWD/install')",
    )


def main(opts):
    context = get_context(opts)
    return run(opts, context)


def get_context(opts):
    update_options(opts)
    return create_context(opts)


def run(opts, context):
    # Load up build type plugin class
    build_type = get_build_type(opts.path)
    build_type_impl = get_class_for_build_type(build_type)()

    pkg_name = context.package_manifest.name

    # Run the uninstall command
    print("+++ Uninstalling '{0}'".format(pkg_name))
    on_uninstall_ret = build_type_impl.on_uninstall(context)
    handle_build_action(on_uninstall_ret, context)


def update_options(opts):
    # use PWD in order to work when being invoked in a symlinked location
    cwd = os.getenv('PWD', os.curdir)
    # no -C / --directory argument yet
    opts.directory = cwd
    opts.path = determine_path_argument(
        cwd, opts.directory, opts.path, os.curdir)
    opts.build_space = determine_path_argument(
        cwd, opts.directory, opts.build_space, 'build')
    opts.install_space = determine_path_argument(
        cwd, opts.directory, opts.install_space, 'install')

    try:
        validate_package_path(opts.path)
    except ValueError as exc:
        sys.exit("Error: {0}".format(exc))


def create_context(opts):
    # Setup build_pkg common context
    context = Context()
    context.source_space = os.path.abspath(os.path.normpath(opts.path))
    context.package_manifest = __get_cached_package_manifest(opts.path)
    pkg_name = context.package_manifest.name
    context.build_space = os.path.join(opts.build_space, pkg_name)
    context.install_space = opts.install_space
    context.build_dependencies = opts.build_dependencies \
        if 'build_dependencies' in opts else []
    print('')
    print("Process package '{0}' with context:".format(pkg_name))
    print("-" * 80)
    keys = [
        'source_space',
        'build_space',
    ]
    max_key_len = str(max([len(k) for k in keys]))
    for key in keys:
        value = context[key]
        if isinstance(value, list):
            value = ", ".join(value) if value else "None"
        print(("{0:>" + max_key_len + "} => {1}").format(key, value))
    print("-" * 80)

    return context
