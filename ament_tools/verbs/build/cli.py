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
import sys

from osrf_pycommon.cli_utils.verb_pattern import call_prepare_arguments

from ament_tools.build_type_discovery import yield_supported_build_types
from ament_tools.helper import argparse_existing_dir
from ament_tools.helper import combine_make_flags
from ament_tools.helper import determine_path_argument
from ament_tools.helper import extract_argument_group
from ament_tools.topological_order import topological_order
from ament_tools.topological_order import topological_order_packages
from ament_tools.verbs import VerbExecutionError
from ament_tools.verbs.build_pkg import main as build_pkg_main
from ament_tools.verbs.build_pkg.cli import add_arguments \
    as build_pkg_add_arguments


def argument_preprocessor(args):
    """Run verb and build_type plugin preprocessors on arguments.

    The preprocessors take in raw arguments and return potentially trimmed
    arguments and extra options to be added to the argparse NameSpace object.

    :param list args: list of arguments as str's
    :returns: tuple of left over arguments and dictionary of extra options
    :raises: SystemError if underlying assumptions are not met
    """
    extras = {}

    # Extract make arguments
    args, make_flags = extract_argument_group(args, '--make-flags')

    # For each available build_type plugin, let it run the preprocessor
    for build_type in yield_supported_build_types():
        build_type_impl = build_type.load()()
        args, tmp_extras = build_type_impl.argument_preprocessor(args)
        extras.update(tmp_extras)

    combine_make_flags(make_flags, args, extras)

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
        '-C', '--directory',
        default=os.curdir,
        help="The base path of the workspace (default '%s')" % os.curdir
    )
    parser.add_argument(
        'basepath',
        nargs='?',
        type=argparse_existing_dir,
        default=os.path.join(os.curdir, 'src'),
        help="Base path to the packages (default 'CWD/src')",
    )
    build_pkg_add_arguments(parser)
    parser.add_argument(
        '--isolated',
        action='store_true',
        default=False,
        help='Use separate subfolders in the install space for each package',
    )
    parser.add_argument(
        '--start-with',
        help='Start with a particular package',
    )

    # Allow all available build_type's to provide additional arguments
    for build_type in yield_supported_build_types():
        build_type_impl = build_type.load()()
        group = parser.add_argument_group("'{0}' build_type options"
                                          .format(build_type_impl.build_type))
        call_prepare_arguments(build_type_impl.prepare_arguments, group, args)

    return parser


def main(opts):
    # use PWD in order to work when being invoked in a symlinked location
    cwd = os.getenv('PWD', os.curdir)
    opts.directory = os.path.abspath(os.path.join(cwd, opts.directory))
    if not os.path.exists(opts.basepath):
        raise RuntimeError("The specified base path '%s' does not exist" %
                           opts.basepath)
    opts.build_space = determine_path_argument(cwd, opts.directory,
                                               opts.build_space, 'build')
    opts.install_space = determine_path_argument(cwd, opts.directory,
                                                 opts.install_space, 'install')

    packages = topological_order(opts.basepath)

    circular_dependencies = [
        package_names for path, package_names, _ in packages if path is None]
    if circular_dependencies:
        raise VerbExecutionError('Circular dependency within the following '
                                 'packages: %s' % circular_dependencies[0])

    print_topological_order(opts, packages)

    iterate_packages(opts, packages, build_pkg_main)


def print_topological_order(opts, packages):
    package_names = [p.name for _, p, _ in packages]

    if opts.start_with and opts.start_with not in package_names:
        sys.exit("Package '{0}' specified with --start-with was not found."
                 .format(opts.start_with))

    print('# Topological order')
    start_with_found = not opts.start_with
    for (path, package, _) in packages:
        if package.name == opts.start_with:
            start_with_found = True
        if not start_with_found:
            print(' skip %s' % package.name)
        else:
            print(' -    %s' % package.name)


def iterate_packages(opts, packages, per_package_callback):
    start_with_found = not opts.start_with
    install_space_base = opts.install_space
    package_dict = dict([(path, package) for path, package, _ in packages])
    for (path, package, depends) in packages:
        if package.name == opts.start_with:
            start_with_found = True
        if not start_with_found:
            print('# Skipping: %s' % package.name)
            continue
        pkg_path = os.path.join(opts.basepath, path)
        opts.path = pkg_path
        if opts.isolated:
            opts.install_space = os.path.join(install_space_base, package.name)

        # get recursive package dependencies in topological order
        ordered_depends = topological_order_packages(
            package_dict, whitelisted=depends)
        ordered_depends = [
            pkg.name
            for _, pkg, _ in ordered_depends
            if pkg.name != package.name]
        # get package share folder for each package
        opts.build_dependencies = []
        for depend in ordered_depends:
            install_space = install_space_base
            if opts.isolated:
                install_space = os.path.join(install_space, depend)
            package_share = os.path.join(install_space, 'share', depend)
            opts.build_dependencies.append(package_share)

        rc = per_package_callback(opts)
        if rc:
            return rc
