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

from __future__ import print_function

import os
import shutil
import sys

from osrf_pycommon.cli_utils.verb_pattern import call_prepare_arguments

from ament_package.templates import configure_file
from ament_package.templates import get_isolated_prefix_level_template_names
from ament_package.templates import get_isolated_prefix_level_template_path
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

    args = combine_make_flags(make_flags, args, extras)

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
    parser.add_argument(
        '--end-with',
        help='End with a particular package',
    )
    parser.add_argument(
        '--only-package',
        '--only',
        help='Only process a particular package, implies --start-with <pkg> and --end-with <pkg>'
    )
    parser.add_argument(
        '--skip-packages',
        nargs='*',
        help='List of packages to skip'
    )

    # Allow all available build_type's to provide additional arguments
    for build_type in yield_supported_build_types():
        build_type_impl = build_type.load()()
        group = parser.add_argument_group("'{0}' build_type options"
                                          .format(build_type_impl.build_type))
        call_prepare_arguments(build_type_impl.prepare_arguments, group, args)

    return parser


def main(opts, per_package_main=build_pkg_main):
    # use PWD in order to work when being invoked in a symlinked location
    cwd = os.getenv('PWD', os.curdir)
    opts.directory = os.path.abspath(os.path.join(cwd, opts.directory))
    if not os.path.exists(opts.basepath):
        raise RuntimeError("The specified base path '%s' does not exist" %
                           opts.basepath)
    opts.build_space = determine_path_argument(
        cwd, opts.directory, opts.build_space,
        'build' if not opts.isolated else 'build_isolated')
    opts.install_space = determine_path_argument(
        cwd, opts.directory, opts.install_space,
        'install' if not opts.isolated else 'install_isolated')

    packages = topological_order(opts.basepath)

    circular_dependencies = [
        package_names for path, package_names, _ in packages if path is None]
    if circular_dependencies:
        raise VerbExecutionError('Circular dependency within the following '
                                 'packages: %s' % circular_dependencies[0])

    print_topological_order(opts, packages)

    iterate_packages(opts, packages, per_package_main)


def print_topological_order(opts, packages):
    package_names = [p.name for _, p, _ in packages]

    if opts.start_with and opts.start_with not in package_names:
        sys.exit("Package '{0}' specified with --start-with was not found."
                 .format(opts.start_with))

    if opts.end_with and opts.end_with not in package_names:
        sys.exit("Package '{0}' specified with --end-with was not found."
                 .format(opts.end_with))

    opts.skip_packages = opts.skip_packages or []
    nonexistent_skip_packages = []
    for skip_package in opts.skip_packages:
        if skip_package not in package_names:
            nonexistent_skip_packages.append(skip_package)
        if skip_package == opts.only_package:
            sys.exit("Cannot --skip-packages and --only-package the same package: '{0}'."
                     .format(skip_package))
    if nonexistent_skip_packages:
            sys.exit('Packages [{0}] specified with --skip-packages were not found.'
                     .format(', '.join(nonexistent_skip_packages)))

    if opts.only_package:
        if opts.start_with or opts.end_with:
            # The argprase mutually exclusive mechanism is broken for subparsers
            # See: http://bugs.python.org/issue10680
            # So we'll check it manually here
            sys.exit("The --start-with and --end-with options cannot be used with "
                     "the --only-package option.")
        if opts.only_package not in package_names:
            sys.exit("Package '{0}' specified with --only-package was not found."
                     .format(opts.only_package))
        opts.start_with = opts.only_package
        opts.end_with = opts.only_package

    if opts.start_with and opts.end_with and not opts.only_package:
        # Make sure that the --end-with doesn't come before the --start-with package.
        test_start_with_found = False
        for (path, package, _) in packages:
            if package.name == opts.start_with:
                test_start_with_found = True
            if package.name == opts.end_with:
                if not test_start_with_found:
                    sys.exit("The --end-with package '{0}' occurs topologically "
                             "before the --start-with package '{1}'"
                             .format(opts.start_with, opts.end_with))
                break

    print('# Topological order')
    start_with_found = not opts.start_with
    end_with_found = not opts.end_with
    for (path, package, _) in packages:
        if package.name == opts.start_with:
            start_with_found = True
        should_skip = False
        if not start_with_found or (opts.end_with and end_with_found):
            should_skip = True
        if package.name in opts.skip_packages:
            should_skip = True
        if should_skip:
            print(' - (%s)' % package.name)
        else:
            print(' - %s' % package.name)
        if package.name == opts.end_with:
            end_with_found = True


def iterate_packages(opts, packages, per_package_callback):
    start_with_found = not opts.start_with
    opts.skip_packages = opts.skip_packages or []
    install_space_base = opts.install_space
    package_dict = dict([(path, package) for path, package, _ in packages])
    workspace_package_names = [pkg.name for pkg in package_dict.values()]
    for (path, package, depends) in packages:
        if package.name == opts.start_with:
            start_with_found = True
        if not start_with_found or package.name in opts.skip_packages:
            print('# Skipping: %s' % package.name)
        else:
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

            # get the package share folder for each exec depend of the package
            opts.exec_dependency_paths_in_workspace = []
            for dep_object in package.exec_depends:
                dep_name = dep_object.name
                if dep_name not in workspace_package_names:
                    # do not add to this list if the dependency is not in the workspace
                    continue
                install_space = install_space_base
                if opts.isolated:
                    install_space = os.path.join(install_space, dep_name)
                package_share = os.path.join(install_space, 'share', dep_name)
                opts.exec_dependency_paths_in_workspace.append(package_share)

            rc = per_package_callback(opts)
            if rc:
                return rc
        if package.name == opts.end_with:
            print("Stopped after package '{0}'".format(package.name))
            break

    # expand prefix-level setup files for the root of the install-space
    if opts.isolated:
        for name in get_isolated_prefix_level_template_names():
            template_path = get_isolated_prefix_level_template_path(name)
            if name.endswith('.in'):
                content = configure_file(template_path, {
                    'CMAKE_INSTALL_PREFIX': install_space_base,
                    'PYTHON_EXECUTABLE': sys.executable,
                })
                destination_path = os.path.join(
                    install_space_base, name[:-3])
                with open(destination_path, 'w') as h:
                    h.write(content)
            else:
                dst = os.path.join(install_space_base, name)
                if os.path.exists(dst):
                    if not opts.symlink_install or \
                            not os.path.islink(dst) or \
                            not os.path.samefile(template_path, dst):
                        os.remove(dst)
                if not os.path.exists(dst):
                    if not opts.symlink_install:
                        shutil.copy(template_path, dst)
                    else:
                        os.symlink(template_path, dst)
