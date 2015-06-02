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

from ament_tools.build_type import BuildAction
from ament_tools.build_type import BuildType

from ament_tools.context import ContextExtender

from ament_tools.helper import extract_argument_group

from ament_tools.build_types.cmake_common import CMAKE_EXECUTABLE
from ament_tools.build_types.cmake_common import cmakecache_exists_at
from ament_tools.build_types.cmake_common import get_visual_studio_version
from ament_tools.build_types.cmake_common import has_make_target
from ament_tools.build_types.cmake_common import MAKE_EXECUTABLE
from ament_tools.build_types.cmake_common import makefile_exists_at
from ament_tools.build_types.cmake_common import MSBUILD_EXECUTABLE
from ament_tools.build_types.cmake_common import project_file_exists_at
from ament_tools.build_types.cmake_common import solution_file_exists_at

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

    def argument_preprocessor(self, args):
        # The CMake pass-through flag collects dashed options.
        # This requires special handling or argparse will complain about
        # unrecognized options.
        args, cmake_args = extract_argument_group(args, '--cmake-args')
        extras = {
            'cmake_args': cmake_args,
        }
        return args, extras

    def extend_context(self, options):
        ce = ContextExtender()
        force_cmake_configure = options.force_cmake_configure
        if getattr(options, 'force_configure', False):
            force_cmake_configure = True
        ce.add('force_cmake_configure', force_cmake_configure)
        ce.add('cmake_args', options.cmake_args)
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
                cmd = prefix + [MAKE_EXECUTABLE, 'test']
                if 'ARGS' not in os.environ:
                    cmd.append('ARGS="-V"')
                yield BuildAction(cmd)
            else:
                self.warn("Could not run tests for '{0}' package because it has no "
                          "'test' target".format(build_type))
        else:
            if MSBUILD_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'msbuild' executable")
            run_tests_project_file = project_file_exists_at(context.build_space, 'RUN_TESTS')
            if run_tests_project_file is not None or context.dry_run:
                yield BuildAction(prefix + [MSBUILD_EXECUTABLE, run_tests_project_file])
            else:
                self.warn("Could not find Visual Studio project file 'RUN_TESTS.vcxproj'")

    def on_install(self, context):
        # Call cmake common on_install (defined in CmakeBuildType)
        for step in self._common_cmake_on_install(context):
            yield step

    def _common_cmake_on_install(self, context):
        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('install', context)

        if not IS_WINDOWS:
            # Assumption: install target exists
            if MAKE_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'make' executable")
            yield BuildAction(prefix + [MAKE_EXECUTABLE, 'install'])
        else:
            if MSBUILD_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'msbuild' executable")
            install_project_file = project_file_exists_at(
                context.build_space, 'INSTALL')
            if install_project_file is None:
                raise VerbExecutionError(
                    "Could not find Visual Studio project file 'INSTALL.vcxproj'")
            yield BuildAction(prefix + [MSBUILD_EXECUTABLE, install_project_file])

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
            'set "CMAKE_PREFIX_PATH=%CMAKE_PREFIX_PATH%;%AMENT_PREFIX_PATH%"')
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
            'export CMAKE_PREFIX_PATH="$CMAKE_PREFIX_PATH:$AMENT_PREFIX_PATH"')

        generated_file = os.path.join(
            context.build_space, '%s__%s.sh' %
            (CmakeBuildType.build_type, name))
        with open(generated_file, 'w') as h:
            for line in lines:
                h.write('%s\n' % line)

        return ['.', generated_file, '&&']
