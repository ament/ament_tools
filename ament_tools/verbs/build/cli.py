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

from collections import OrderedDict
from concurrent.futures import CancelledError
from concurrent.futures import FIRST_COMPLETED
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
import copy
from multiprocessing import cpu_count
import os
import shutil
import sys

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

from osrf_pycommon.cli_utils.verb_pattern import call_prepare_arguments


def argument_preprocessor(args):
    """
    Run verb and build_type plugin preprocessors on arguments.

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
    """
    Add parameters to argparse for the build verb and available plugins.

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
        help="The base path of the workspace (default '%s')" % os.curdir,
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
        '--only-packages',
        nargs='+', default=[],
        help='Only process a particular set of packages',
    )
    parser.add_argument(
        '--skip-packages',
        nargs='*', default=[],
        help='Set of packages to skip',
    )
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Enable building packages in parallel',
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

    pkg_names = [p.name for _, p, _ in packages]
    check_opts(opts, pkg_names)
    consolidate_package_selection(opts, pkg_names)
    print_topological_order(opts, pkg_names)

    if set(pkg_names) <= set(opts.skip_packages):
        print('All selected packages are being skipped. Nothing to do.',
              file=sys.stderr)
        return 0

    return iterate_packages(opts, packages, per_package_main)


def check_opts(opts, package_names):
    if opts.start_with and opts.start_with not in package_names:
        sys.exit("Package '{0}' specified with --start-with was not found."
                 .format(opts.start_with))

    if opts.end_with and opts.end_with not in package_names:
        sys.exit("Package '{0}' specified with --end-with was not found."
                 .format(opts.end_with))

    nonexistent_skip_packages = set(opts.skip_packages) - set(package_names)
    if nonexistent_skip_packages:
        sys.exit('Packages [{0}] specified with --skip-packages were not found.'
                 .format(', '.join(sorted(nonexistent_skip_packages))))

    if opts.only_packages:
        if opts.start_with or opts.end_with:
            # The argprase mutually exclusive mechanism is broken for subparsers
            # See: http://bugs.python.org/issue10680
            # So we'll check it manually here
            sys.exit('The --start-with and --end-with options cannot be used with '
                     'the --only-packages option.')
        for only_package in opts.only_packages:
            if only_package not in package_names:
                sys.exit("Package '{0}' specified with --only-packages was not found."
                         .format(only_package))

    if opts.start_with and opts.end_with:
        # Make sure that the --end-with doesn't come before the --start-with package.
        test_start_with_found = False
        for pkg_name in package_names:
            if pkg_name == opts.start_with:
                test_start_with_found = True
            if pkg_name == opts.end_with:
                if not test_start_with_found:
                    sys.exit("The --end-with package '{0}' occurs topologically "
                             "before the --start-with package '{1}'"
                             .format(opts.end_with, opts.start_with))
                break


def consolidate_package_selection(opts, package_names):
    # after this function opts.skip_packages will contain the information from:
    # start_with, end_with, only_packages
    start_with_found = not opts.start_with
    end_with_found = not opts.end_with
    for pkg_name in package_names:
        if pkg_name == opts.start_with:
            start_with_found = True
        should_skip = False
        if not start_with_found or (opts.end_with and end_with_found):
            should_skip = True
        if opts.only_packages and pkg_name not in opts.only_packages:
            should_skip = True
        if should_skip:
            if pkg_name not in opts.skip_packages:
                opts.skip_packages.append(pkg_name)
        if pkg_name == opts.end_with:
            end_with_found = True


def print_topological_order(opts, package_names):
    print('# Topological order')
    for pkg_name in package_names:
        if pkg_name in opts.skip_packages:
            print(' - ( %s )' % pkg_name)
        else:
            print(' - %s' % pkg_name)


def iterate_packages(opts, packages, per_package_callback):
    install_space_base = opts.install_space
    package_dict = {path: package for path, package, _ in packages}
    workspace_package_names = [pkg.name for pkg in package_dict.values()]
    jobs = OrderedDict()
    for (path, package, depends) in packages:
        if package.name in opts.skip_packages:
            print('# Skipping: %s' % package.name)
        else:
            pkg_path = os.path.join(opts.basepath, path)
            package_opts = copy.copy(opts)
            package_opts.path = os.path.abspath(os.path.join(os.getcwd(), pkg_path))
            if package_opts.isolated:
                package_opts.install_space = os.path.join(install_space_base, package.name)

            # get recursive package dependencies in topological order
            ordered_depends = topological_order_packages(
                package_dict, whitelisted=depends)
            ordered_depends = [
                pkg.name
                for _, pkg, _ in ordered_depends
                if pkg.name != package.name]
            # get package share folder for each package
            package_opts.build_dependencies = []
            for depend in ordered_depends:
                install_space = install_space_base
                if package_opts.isolated:
                    install_space = os.path.join(install_space, depend)
                package_share = os.path.join(install_space, 'share', depend)
                package_opts.build_dependencies.append(package_share)

            # get the package share folder for each exec depend of the package
            package_opts.exec_dependency_paths_in_workspace = []
            for dep_object in package.exec_depends:
                dep_name = dep_object.name
                if dep_name not in workspace_package_names:
                    # do not add to this list if the dependency is not in the workspace
                    continue
                install_space = install_space_base
                if package_opts.isolated:
                    install_space = os.path.join(install_space, dep_name)
                package_share = os.path.join(install_space, 'share', dep_name)
                package_opts.exec_dependency_paths_in_workspace.append(package_share)

            jobs[package.name] = {
                'callback': per_package_callback,
                'opts': package_opts,
                'depends': ordered_depends,
            }
        if package.name == opts.end_with:
            break

    if not opts.parallel:
        rc = process_sequentially(jobs)
    else:
        rc = process_in_parallel(jobs)

    if not rc and opts.end_with:
        print("Stopped after package '{0}'".format(opts.end_with))

    # expand prefix-level setup files for the root of the install-space
    if opts.isolated:
        for name in get_isolated_prefix_level_template_names():
            template_path = get_isolated_prefix_level_template_path(name)
            if name.endswith('.in'):
                content = configure_file(template_path, {
                    'CMAKE_INSTALL_PREFIX': install_space_base,
                    'PYTHON_EXECUTABLE': opts.python_interpreter,
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

    return rc


def process_sequentially(jobs):
    rc = 0
    for package_name in jobs:
        job = jobs[package_name]
        rc = job['callback'](job['opts'])
        if rc:
            return rc
    return rc


def process_in_parallel(jobs):
    for package_name, job in jobs.items():
        job['depends'] = [n for n in job['depends'] if n in jobs.keys()]
    max_workers = cpu_count()
    threadpool = ThreadPoolExecutor(max_workers=max_workers)
    futures = {}
    finished_jobs = {}
    rc = 0
    while jobs or futures:
        # take "ready" jobs
        ready_jobs = []
        for package_name, job in jobs.items():
            if len(futures) + len(ready_jobs) >= max_workers:
                # don't schedule more jobs then workers
                # to prevent starting further jobs when a job fails
                break
            if not set(job['depends']) - set(finished_jobs.keys()):
                ready_jobs.append((package_name, job))
        for package_name, _ in ready_jobs:
            del jobs[package_name]

        # pass them to the executor
        for package_name, job in ready_jobs:
            future = threadpool.submit(job['callback'], job['opts'])
            futures[future] = package_name

        # wait for futures
        assert futures
        done_futures, _ = wait(futures.keys(), timeout=60, return_when=FIRST_COMPLETED)

        if not done_futures:  # timeout
            print('[Waiting for: %s]' % ', '.join(sorted(futures.values())))

        # check result of done futures
        for done_future in done_futures:
            package_name = futures[done_future]
            del futures[done_future]
            try:
                result = done_future.result()
            except CancelledError:
                # since the job hasn't been cancelled before completing
                continue
            except (Exception, SystemExit) as e:
                print('%s in %s: %s' % (type(e).__name__, package_name, e), file=sys.stderr)
                import traceback
                traceback.print_exc()
                result = 1
            finished_jobs[package_name] = result
            if result and not rc:
                rc = result

        # if any job failed cancel pending futures
        if rc:
            for future in futures:
                future.cancel()
            break

    threadpool.shutdown()

    if any(finished_jobs.values()):
        failed_jobs = {
            package_name: result for (package_name, result) in finished_jobs.items() if result}
        print('Failed packages: ' + ', '.join([x for x in failed_jobs]), file=sys.stderr)

    return rc
