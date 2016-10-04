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

from __future__ import print_function

import os

from ament_tools.helper import argparse_existing_dir
from ament_tools.helper import determine_path_argument
from ament_tools.topological_order import topological_order
from ament_tools.topological_order import topological_order_packages
from ament_tools.verbs import VerbExecutionError
from ament_tools.verbs.build.cli import print_topological_order
from ament_tools.verbs.uninstall_pkg import main as uninstall_pkg_main
from ament_tools.verbs.uninstall_pkg.cli import add_arguments \
    as uninstall_pkg_add_arguments


def prepare_arguments(parser, args):
    """
    Add parameters to argparse for the uninstall verb and available plugins.

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
    uninstall_pkg_add_arguments(parser)
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

    return parser


def main(opts, per_package_main=uninstall_pkg_main):
    # use PWD in order to work when being invoked in a symlinked location
    cwd = os.getenv('PWD', os.curdir)
    opts.directory = os.path.abspath(os.path.join(cwd, opts.directory))
    if not os.path.exists(opts.basepath):
        raise RuntimeError("The specified base path '%s' does not exist" %
                           opts.basepath)
    opts.build_space = determine_path_argument(
        cwd, opts.directory, opts.build_space, 'build')
    opts.install_space = determine_path_argument(
        cwd, opts.directory, opts.install_space, 'install')

    packages = topological_order(opts.basepath)

    circular_dependencies = [
        package_names for path, package_names, _ in packages if path is None]
    if circular_dependencies:
        raise VerbExecutionError('Circular dependency within the following '
                                 'packages: %s' % circular_dependencies[0])

    print_topological_order(opts, packages)

    iterate_packages(opts, packages, per_package_main)


def iterate_packages(opts, packages, per_package_callback):
    end_with_found = not opts.end_with
    package_dict = dict([(path, package) for path, package, _ in packages])
    for (path, package, depends) in reversed(packages):
        if package.name == opts.end_with:
            end_with_found = True
        if not end_with_found:
            print('# Skipping: %s' % package.name)
            continue
        pkg_path = os.path.join(opts.basepath, path)
        opts.path = pkg_path

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
            package_share = os.path.join(opts.install_space, 'share', depend)
            opts.build_dependencies.append(package_share)

        rc = per_package_callback(opts)
        if rc:
            return rc
        if package.name == opts.start_with:
            print("Stopped after package '{0}'".format(package.name))
            break
