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

import argparse
import inspect
import os
import shlex
import subprocess
import sys

from ament_package.templates import configure_file
from ament_package.templates import get_prefix_level_template_names
from ament_package.templates import get_prefix_level_template_path

from ament_tools.build_type_discovery import get_class_for_build_type
from ament_tools.build_type_discovery import MissingPluginError
from ament_tools.context import Context
from ament_tools.helper import combine_make_flags
from ament_tools.helper import deploy_file
from ament_tools.helper import determine_path_argument
from ament_tools.helper import extract_argument_group
from ament_tools.package_types import package_exists_at
from ament_tools.package_types import parse_package

from osrf_pycommon.cli_utils.verb_pattern import call_prepare_arguments


def add_path_argument(parser):
    """Add position path argument to parser."""
    parser.add_argument(
        'path',
        nargs='?',
        default=os.curdir,
        help='Path to the package',
    )


def argument_preprocessor(args):
    """
    Run verb and plugin preprocessors on arguments.

    The preprocessors take in raw arguments and return potentially trimmed
    arguments and extra options to be added to the argparse NameSpace object.

    This can fail if the positional path argument does not contain a valid path
    or if the build type of the package at that path does not have a
    corresponding build type plugin.

    :param list args: list of arguments as str's
    :returns: tuple of left over arguments and dictionary of extra options
    :raises: SystemError if underlying assumptions are not met
    """
    extras = {}

    # Extract make arguments
    args, make_flags = extract_argument_group(args, '--make-flags')

    # Detected build type if possible
    parser = argparse.ArgumentParser()
    add_path_argument(parser)
    opts, _ = parser.parse_known_args(args)
    try:
        validate_package_path(opts.path)
    except (MissingPluginError, ValueError) as exc:
        sys.exit('{0}'.format(exc))
    build_type = get_build_type(opts.path)
    build_type_impl = get_class_for_build_type(build_type)()
    # Let detected build type plugin do argument preprocessing
    args, extras = build_type_impl.argument_preprocessor(args)

    args = combine_make_flags(make_flags, args, extras)

    return args, extras


def prepare_arguments(parser, args):
    """
    Add parameters to argparse for the build_pkg verb and its plugins.

    After adding the generic verb arguments, this function tries to determine
    the build type of the target package. This is done by gracefully trying
    to get the positional ``path`` argument from the arguments, falling back
    to the default ``os.curdir``. Then it searches for a package manifest in
    that path. If it finds the package manifest it then determines the build
    type of the package, e.g. ``ament_cmake``. It then tries to load a build
    type plugin for that build type. If the loading is successful it will allow
    the plugin to add additional arguments to the parser in a new
    :py:class:`argparse.ArgumentGroup` for that build type.

    :param parser: ArgumentParser object to which arguments are added
    :type parser: :py:class:`argparse.ArgumentParser`
    :param list args: list of arguments as str's
    :returns: modified version of the original parser given
    :rtype: :py:class:`argparse.ArgumentParser`
    """
    # Add verb arguments
    add_path_argument(parser)
    add_arguments(parser)

    # Detected build type if possible
    try:
        # Remove -h and --help to prevent printing help messages
        filt_args = list(filter(lambda x: x not in ['-h', '--help'], args))
        # Remove first position argument, because that will be the verb
        for i, arg in enumerate(filt_args):
            if not arg.startswith('-'):
                del filt_args[i]
                break
        # Parse the arguments to find the user's provided path (or the default)
        opts, _ = parser.parse_known_args(filt_args)
        # Check to ensure the path has a package
        validate_package_path(opts.path)
        # Get the build_type from the package manifest
        build_type = get_build_type(opts.path)
        # Find an entry point which supports this build type
        build_type_impl = get_class_for_build_type(build_type)()
        # Let the detected build type plugin add arguments
        group = parser.add_argument_group(
            '{0} (detected) options'.format(build_type_impl.build_type))
        call_prepare_arguments(
            build_type_impl.prepare_arguments,
            group,
            args,
        )
    # Catch value and system errors which will raise later
    # This is done to preserve -h and --help's ability to function
    except (MissingPluginError, ValueError) as exc:
        # If system exit AND -h or --help are used, show the error
        if '-h' in args or '--help' in args:
            print('Error: Could not detect package build type:', exc)
    return parser


def add_arguments(parser):
    parser.add_argument(
        '--build-space',
        help="Path to the build space (default 'CWD/build(_isolated)')",
    )
    parser.add_argument(
        '--install-space',
        help="Path to the install space (default 'CWD/install(_isolated)')",
    )
    parser.add_argument(
        '--build-tests',
        action='store_true',
        default=False,
        help='Enable building tests',
    )
    parser.add_argument(
        '--make-flags',
        nargs='*',
        default=[],
        help='Flags to be passed to make by build types which invoke make',
    )
    parser.add_argument(
        '--skip-build',
        action='store_true',
        default=False,
        help='Skip the build step (this can be used when installing or '
             'testing and you know that the build has successfully run)',
    )
    parser.add_argument(
        '--skip-install',
        action='store_true',
        default=False,
        help='Skip the install step (only makes sense when install has been '
             'done before using symlinks and no new files have been added or '
             'when testing after a successful install)',
    )
    parser.add_argument(
        '-s',
        '--symlink-install',
        action='store_true',
        default=False,
        help='Use symlinks instead of copying files wherever possible',
    )
    parser.add_argument(
        '--python-interpreter',
        default=sys.executable,
        help='Use a different Python interpreter for invoking subprocesses'
             " (default '%s')" % sys.executable,
    )


package_manifest_cache_ = {}


def _get_cached_package_manifest(path):
    global package_manifest_cache_
    if path not in package_manifest_cache_:
        package_manifest_cache_[path] = parse_package(path)
    return package_manifest_cache_[path]


def get_build_type(path):
    """
    Extract the build_type from the package manifest at the given path.

    :param str path: path to a package manifest file
    :returns: build_type as a string
    """
    package = _get_cached_package_manifest(path)

    build_type_exports = [e for e in package.exports
                          if e.tagname == 'build_type']
    if len(build_type_exports) > 1:
        print("The package in '%s' exports multiple build types" % path,
              file=sys.stderr)

    default_build_type = '<not-specified>'
    if not build_type_exports:
        return default_build_type

    return build_type_exports[0].content


def validate_package_path(path):
    """
    Assert the given path is a directory with a package.

    :param str path: directory containing a package
    :raises: ValueError if path is not valid or does not contain a package
    """
    if not os.path.isdir(path):
        raise ValueError("Path '{0}' is not a directory or does not exist"
                         .format(path))
    if not package_exists_at(path):
        raise ValueError("Path '{0}' does not contain a package".format(path))


def run_command(build_action, context):
    cwd = build_action.cwd
    if cwd is None:
        cwd = context.build_space
    print("==> '{0}' in '{1}'".format(' '.join(build_action.cmd), cwd))
    # flush Python output before letting the external command write to the pipe
    sys.stdout.flush()
    try:
        cmd = build_action.cmd
        if os.name != 'nt':
            cmd = ' '.join([(shlex.quote(c) if c != '&&' else c) for c in cmd])
        subprocess.check_call(cmd, shell=True, cwd=cwd, env=build_action.env)
    except subprocess.CalledProcessError as exc:
        print()
        cmd_msg = exc.cmd
        if isinstance(cmd_msg, list):
            cmd_msg = ' '.join(cmd_msg)
        msg = "<== Command '{0}' failed in '{1}' with exit code '{2}'" \
            .format(cmd_msg, cwd, exc.returncode)
        print(msg, file=sys.stderr)
        sys.exit(msg)


def handle_build_action(build_action_ret, context):
    if not inspect.isgenerator(build_action_ret):
        return
    for build_action in build_action_ret:
        if build_action.type == 'command':
            run_command(build_action, context)
        elif build_action.type == 'function':
            build_action.cmd(context)
        else:
            raise RuntimeError("Unknown BuildAction type '{0}'"
                               .format(build_action.type))


def main(opts):
    context = get_context(opts)
    return run(opts, context)


def get_context(opts):
    update_options(opts)
    return create_context(opts)


def expand_prefix_level_setup_files(context):
    # expand prefix-level setup files
    for name in get_prefix_level_template_names():
        if name.endswith('.in'):
            template_path = get_prefix_level_template_path(name)
            content = configure_file(template_path, {
                'CMAKE_INSTALL_PREFIX': context.install_space,
                'PYTHON_EXECUTABLE': context.python_interpreter,
            })
            destination_path = os.path.join(
                context.build_space, name[:-3])
            with open(destination_path, 'w') as h:
                h.write(content)


def deploy_prefix_level_setup_files(context):
    # deploy prefix-level setup files
    for name in get_prefix_level_template_names():
        if name.endswith('.in'):
            deploy_file(context, context.build_space, name[:-3])
        else:
            template_path = get_prefix_level_template_path(name)
            deploy_file(
                context, os.path.dirname(template_path), os.path.basename(template_path))


def run(opts, context):
    # Load up build type plugin class
    build_type = get_build_type(opts.path)
    build_type_impl = get_class_for_build_type(build_type)()

    pkg_name = context.package_manifest.name

    if not opts.skip_build:
        ignore_file = os.path.join(context.build_space, 'AMENT_IGNORE')
        if not os.path.exists(ignore_file) and not context.dry_run:
            os.makedirs(context.build_space, exist_ok=True)
            with open(ignore_file, 'w'):
                pass

        # Run the build command
        print("+++ Building '{0}'".format(pkg_name))
        on_build_ret = build_type_impl.on_build(context)
        handle_build_action(on_build_ret, context)
        expand_prefix_level_setup_files(context)

    if not opts.skip_install:
        # Run the install command
        print("+++ Installing '{0}'".format(pkg_name))
        on_install_ret = build_type_impl.on_install(context)
        handle_build_action(on_install_ret, context)
        deploy_prefix_level_setup_files(context)


def update_options(opts):
    # use PWD in order to work when being invoked in a symlinked location
    cwd = os.getenv('PWD', os.curdir)
    # no -C / --directory argument yet
    opts.directory = cwd
    opts.path = determine_path_argument(cwd, opts.directory, opts.path,
                                        os.curdir)
    opts.build_space = determine_path_argument(cwd, opts.directory,
                                               opts.build_space, 'build')
    opts.install_space = determine_path_argument(cwd, opts.directory,
                                                 opts.install_space, 'install')

    try:
        validate_package_path(opts.path)
    except ValueError as exc:
        sys.exit('Error: {0}'.format(exc))


def create_context(opts):
    # Setup build_pkg common context
    context = Context()
    context.source_space = os.path.abspath(os.path.normpath(opts.path))
    context.package_manifest = _get_cached_package_manifest(opts.path)
    pkg_name = context.package_manifest.name
    context.build_space = os.path.join(opts.build_space, pkg_name)
    context.install_space = opts.install_space
    context.install = True
    context.build_dependencies = opts.build_dependencies \
        if 'build_dependencies' in opts else []
    context.exec_dependency_paths_in_workspace = opts.exec_dependency_paths_in_workspace \
        if 'exec_dependency_paths_in_workspace' in opts else []
    context.symlink_install = opts.symlink_install
    context.make_flags = opts.make_flags
    context.dry_run = False
    context.build_tests = opts.build_tests
    context.python_interpreter = opts.python_interpreter
    print('')
    print("Process package '{0}' with context:".format(pkg_name))
    print('-' * 80)
    keys = [
        'source_space',
        'build_space',
        'install_space',
        'make_flags',
        'build_tests',
    ]
    max_key_len = str(max(len(k) for k in keys))
    for key in keys:
        value = context[key]
        if isinstance(value, list):
            value = ', '.join(value) if value else 'None'
        print(('{0:>' + max_key_len + '} => {1}').format(key, value))
    print('-' * 80)

    # Load up build type plugin class
    build_type = get_build_type(opts.path)
    build_type_impl = get_class_for_build_type(build_type)()

    # Allow the build type plugin to process options into a context extender
    ce = build_type_impl.extend_context(opts)
    # Extend the context with the context extender
    ce.apply_to_context(context)

    return context
