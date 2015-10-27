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

"""Implements the BuildType support for cmake based ament packages."""

import os

from ament_package.templates import get_environment_hook_template_path

from ament_tools.build_type import BuildAction
from ament_tools.build_type import BuildType

from ament_tools.context import ContextExtender

from ament_tools.helper import compute_deploy_destination
from ament_tools.helper import deploy_file
from ament_tools.helper import extract_argument_group

from ament_tools.build_types.cmake_common import CMAKE_EXECUTABLE
from ament_tools.build_types.cmake_common import CTEST_EXECUTABLE
from ament_tools.build_types.cmake_common import cmakecache_exists_at
from ament_tools.build_types.cmake_common import get_visual_studio_version
from ament_tools.build_types.cmake_common import has_make_target
from ament_tools.build_types.cmake_common import MAKE_EXECUTABLE
from ament_tools.build_types.cmake_common import makefile_exists_at
from ament_tools.build_types.cmake_common import MSBUILD_EXECUTABLE
from ament_tools.build_types.cmake_common import project_file_exists_at
from ament_tools.build_types.cmake_common import solution_file_exists_at

from ament_tools.build_types.common import expand_package_level_setup_files
from ament_tools.build_types.common import get_cached_config
from ament_tools.build_types.common import set_cached_config

from ament_tools.verbs import VerbExecutionError

IS_WINDOWS = os.name == 'nt'


class CmakeBuildType(BuildType):
    build_type = 'cmake'
    description = "plain cmake project"

    def prepare_arguments(self, parser):
        parser.add_argument(
            '--force-cmake-configure',
            action='store_true',
            help="Invoke 'cmake' even if it has been executed before.")
        parser.add_argument(
            '--cmake-args',
            nargs='*',
            default=[],
            help="Arbitrary arguments which are passed to all CMake projects. "
                 "Argument collection can be terminated with '--'.")
        parser.add_argument(
            '--ctest-args',
            nargs='*',
            default=[],
            help="Arbitrary arguments which are passed to all CTest invocations. "
                 "The option is only used by the 'test*' verbs. "
                 "Argument collection can be terminated with '--'.")

    def argument_preprocessor(self, args):
        # The CMake pass-through flag collects dashed options.
        # This requires special handling or argparse will complain about
        # unrecognized options.
        args, cmake_args = extract_argument_group(args, '--cmake-args')
        args, ctest_args = extract_argument_group(args, '--ctest-args')
        extras = {
            'cmake_args': cmake_args,
            'ctest_args': ctest_args,
        }
        return args, extras

    def extend_context(self, options):
        ce = ContextExtender()
        force_cmake_configure = options.force_cmake_configure
        if getattr(options, 'force_configure', False):
            force_cmake_configure = True
        ce.add('force_cmake_configure', force_cmake_configure)
        ce.add('cmake_args', options.cmake_args)
        ce.add('ctest_args', options.ctest_args)
        return ce

    def on_build(self, context):
        # Regardless of dry-run, try to determine if CMake should be invoked
        should_run_configure = False
        if context.force_cmake_configure:
            should_run_configure = True
        elif not makefile_exists_at(context.build_space) or \
                not cmakecache_exists_at(context.build_space):
            # If either the Makefile or the CMake cache does not exist
            # we must configure
            should_run_configure = True
        cached_cmake_config = get_cached_config(
            context.build_space, 'cmake_args')
        cmake_config = {
            'cmake_args': context.cmake_args,
            'build_tests': context.build_tests,
            'symlink_install': context.symlink_install,
        }
        if cmake_config != cached_cmake_config:
            should_run_configure = True
            self.warn("Running cmake because arguments have changed.")
        # Store the cmake_args for next invocation
        set_cached_config(context.build_space, 'cmake_args',
                          cmake_config)
        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('build', context)
        # Calculate any extra cmake args which are not common between cmake build types
        extra_cmake_args = []
        if should_run_configure:
            extra_cmake_args += context.cmake_args
        # Yield the cmake common on_build
        for step in self._common_cmake_on_build(
            should_run_configure, context, prefix, extra_cmake_args
        ):
            yield step

    def _common_cmake_on_build(self, should_run_configure, context, prefix, extra_cmake_args):
        # Execute the configure step
        # (either cmake or the cmake_check_build_system make target)
        if should_run_configure:
            cmake_args = [context.source_space]
            cmake_args.extend(extra_cmake_args)
            cmake_args += ["-DCMAKE_INSTALL_PREFIX=" + context.install_space]
            if IS_WINDOWS:
                vsv = get_visual_studio_version()
                if vsv is None:
                    print("VisualStudioVersion is not set, please run within "
                          "a VS2013 or VS2015 Command Prompt.")
                    raise VerbExecutionError(
                        "Could not determine Visual Studio Version.")
                generator = None
                if vsv == '12.0':
                    generator = 'Visual Studio 12 2013 Win64'
                elif vsv == '14.0':
                    generator = 'Visual Studio 14 2015 Win64'
                else:
                    raise VerbExecutionError("Unknown VS version: " + vsv)
                cmake_args += ['-G', generator]
            if CMAKE_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'cmake' executable")
            yield BuildAction(prefix + [CMAKE_EXECUTABLE] + cmake_args)
        elif not IS_WINDOWS:  # Check for reconfigure if available.
            if MAKE_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'make' executable")
            cmd = prefix + [MAKE_EXECUTABLE, 'cmake_check_build_system']
            yield BuildAction(cmd)
        # Now execute the build step
        if not IS_WINDOWS:
            if MAKE_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'make' executable")
            yield BuildAction(prefix + [MAKE_EXECUTABLE] + context.make_flags)
        else:
            if MSBUILD_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'msbuild' executable")
            solution_file = solution_file_exists_at(
                context.build_space, context.package_manifest.name)
            if '-j1' in context.make_flags:
                yield BuildAction(prefix + [MSBUILD_EXECUTABLE, solution_file])
            else:
                yield BuildAction(prefix + [MSBUILD_EXECUTABLE, '/m', solution_file])

    def on_test(self, context):
        for step in self._common_cmake_on_test(context, 'cmake'):
            yield step

    def _common_cmake_on_test(self, context, build_type):
        assert context.build_tests
        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('test', context)
        if not IS_WINDOWS:
            if has_make_target(context.build_space, 'test') or context.dry_run:
                if MAKE_EXECUTABLE is None:
                    raise VerbExecutionError("Could not find 'make' executable")
                cmd = prefix + [MAKE_EXECUTABLE, 'test']
                if 'ARGS' not in os.environ:
                    args = ['-V']
                elif os.environ['ARGS']:
                    args = [os.environ['ARGS']]
                else:
                    args = []
                args += context.ctest_args
                if args:
                    # the valus is not quoted here
                    # since each item will be quoted by shlex.quote later if necessary
                    cmd.append('ARGS=%s' % ' '.join(args))
                yield BuildAction(cmd)
            else:
                self.warn("Could not run tests for '{0}' package because it has no "
                          "'test' target".format(build_type))
        else:
            if CTEST_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'ctest' executable")
            # invoke CTest directly in order to pass arguments
            # it needs a specific configuration and currently there are no conf. specific tests
            yield BuildAction(prefix + [
                CTEST_EXECUTABLE,
                # choose configuration on e.g. Windows
                '-C', 'Debug',
                # generate xml of test summary
                '-D', 'ExperimentalTest', '--no-compress-output',
                # show all test output
                '-V',
                '--force-new-ctest-process'] +
                context.ctest_args)

    def on_install(self, context):
        # First determine the files being deployed with skip_if_exists=True and remove them.
        environment_hooks_path = \
            os.path.join('share', context.package_manifest.name, 'environment')

        environment_hooks_to_be_deployed = []

        # Prepare to deploy PATH environment hook
        ext = '.sh' if not IS_WINDOWS else '.bat'
        path_template_path = get_environment_hook_template_path('path' + ext)
        environment_hooks_to_be_deployed.append(path_template_path)
        environment_hooks = [os.path.join(environment_hooks_path, 'path' + ext)]

        # Prepare to deploy library path environment hook if not on Windows
        if not IS_WINDOWS:
            library_template_path = get_environment_hook_template_path('library_path.sh')
            environment_hooks_to_be_deployed.append(library_template_path)
            environment_hooks.append(os.path.join(environment_hooks_path, 'library_path.sh'))

        # Expand package level setup files
        destinations = \
            expand_package_level_setup_files(context, environment_hooks, environment_hooks_path)

        # Remove package level setup files so they can be replaced correctly either in the
        # cmake install step or later with deploy_file(..., skip_if_exists=True)
        for destination in destinations:
            destination_path = compute_deploy_destination(
                context,
                os.path.basename(destination),
                os.path.dirname(os.path.relpath(destination, context.build_space))
            )
            if os.path.exists(destination_path):
                os.unlink(destination_path)

        # Call cmake common on_install (defined in CmakeBuildType)
        for step in self._common_cmake_on_install(context):
            yield step

        # Install files needed to extend the environment for build dependents to use this package
        # create marker file
        marker_file = os.path.join(
            context.install_space,
            'share', 'ament_index', 'resource_index', 'packages',
            context.package_manifest.name)
        if not os.path.exists(marker_file):
            marker_dir = os.path.dirname(marker_file)
            if not os.path.exists(marker_dir):
                os.makedirs(marker_dir)
            with open(marker_file, 'w'):  # "touching" the file
                pass

        # Deploy environment hooks
        for environment_hook in environment_hooks_to_be_deployed:
            deploy_file(
                context, os.path.dirname(environment_hook), os.path.basename(environment_hook),
                dst_subfolder=environment_hooks_path)

        # Expand package-level setup files
        for destination in destinations:
            deploy_file(
                context,
                os.path.dirname(destination), os.path.basename(destination),
                dst_subfolder=os.path.dirname(os.path.relpath(destination, context.build_space)),
                skip_if_exists=True)

    def _common_cmake_on_install(self, context):
        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('install', context)

        if not IS_WINDOWS:
            if has_make_target(context.build_space, 'install') or context.dry_run:
                if MAKE_EXECUTABLE is None:
                    raise VerbExecutionError("Could not find 'make' executable")
                yield BuildAction(prefix + [MAKE_EXECUTABLE, 'install'])
            else:
                self.warn('Could not run installation for package because it has no '
                          "'install' target")
        else:
            install_project_file = project_file_exists_at(
                context.build_space, 'INSTALL')
            if install_project_file is not None:
                if MSBUILD_EXECUTABLE is None:
                    raise VerbExecutionError("Could not find 'msbuild' executable")
                yield BuildAction(prefix + [MSBUILD_EXECUTABLE, install_project_file])
            else:
                self.warn("Could not find Visual Studio project file 'INSTALL.vcxproj'")

    def on_uninstall(self, context):
        # Call cmake common on_uninstall (defined in CmakeBuildType)
        for step in self._common_cmake_on_uninstall(context, 'cmake'):
            yield step

    def _common_cmake_on_uninstall(self, context, build_type):
        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('uninstall', context)

        if not IS_WINDOWS:
            if has_make_target(context.build_space, 'uninstall'):
                if MAKE_EXECUTABLE is None:
                    raise VerbExecutionError("Could not find 'make' executable")
                cmd = prefix + [MAKE_EXECUTABLE, 'uninstall']
                yield BuildAction(cmd)
            else:
                self.warn("Could not run uninstall for '{0}' package because it has no "
                          "'uninstall' target".format(build_type))
        else:
            if MSBUILD_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'msbuild' executable")
            uninstall_project_file = project_file_exists_at(context.build_space, 'UNINSTALL')
            if uninstall_project_file is not None:
                yield BuildAction(prefix + [MSBUILD_EXECUTABLE, uninstall_project_file])
            else:
                self.warn("Could not find Visual Studio project file 'UNINSTALL.vcxproj'")

    def _get_command_prefix(self, name, context):
        if not IS_WINDOWS:
            return self._get_command_prefix_unix(name, context)
        else:
            return self._get_command_prefix_windows(name, context)

    def _get_command_prefix_windows(self, name, context):
        lines = []
        lines.append('@echo off\n')
        lines.append('if defined AMENT_TRACE_SETUP_FILES echo Inside %~0')
        for path in context.build_dependencies:
            local_setup = os.path.join(path, 'local_setup.bat')
            lines.append('if exist "{0}" call "{0}"\n'.format(local_setup))
        lines.append(
            'set "CMAKE_PREFIX_PATH=%AMENT_PREFIX_PATH%;%CMAKE_PREFIX_PATH%"')
        lines.append('%*')
        lines.append('if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%')
        lines.append('if defined AMENT_TRACE_SETUP_FILES echo Leaving %~0')

        generated_file = os.path.join(
            context.build_space, '%s__%s.bat' %
            (CmakeBuildType.build_type, name))
        with open(generated_file, 'w') as h:
            for line in lines:
                h.write('%s\n' % line)

        return [generated_file]

    def _get_command_prefix_unix(self, name, context):
        lines = []
        lines.append('#!/usr/bin/env sh\n')
        for path in context.build_dependencies:
            local_setup = os.path.join(path, 'local_setup.sh')
            lines.append('if [ -f "%s" ]; then' % local_setup)
            lines.append('  . "%s"' % local_setup)
            lines.append('fi')
        lines.append(
            'export CMAKE_PREFIX_PATH="$AMENT_PREFIX_PATH:$CMAKE_PREFIX_PATH"')

        generated_file = os.path.join(
            context.build_space, '%s__%s.sh' %
            (CmakeBuildType.build_type, name))
        with open(generated_file, 'w') as h:
            for line in lines:
                h.write('%s\n' % line)

        return ['.', generated_file, '&&']
