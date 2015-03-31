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


class AmentCmakeBuildType(BuildType):
    build_type = 'ament_cmake'
    description = "ament package built with cmake"

    def prepare_arguments(self, parser):
        parser.add_argument(
            '--force-ament-cmake-configure',
            action='store_true',
            help="Invoke 'cmake' even if it has been executed before.")
        parser.add_argument(
            '--ament-cmake-args',
            nargs='*',
            default=[],
            help='Arbitrary arguments which are passed to CMake. '
                 'It must be passed after other arguments since it collects '
                 'all following options.')

    def argument_preprocessor(self, args):
        # The ament CMake pass-through flag collects dashed options.
        # This requires special handling or argparse will complain about
        # unrecognized options.
        args, cmake_args = extract_argument_group(args, '--ament-cmake-args')
        extras = {
            'ament_cmake_args': cmake_args,
        }
        return args, extras

    def extend_context(self, options):
        ce = ContextExtender()
        force_ament_cmake_configure = options.force_ament_cmake_configure
        if hasattr(options, 'force_configure') and options.force_configure:
            force_ament_cmake_configure = True
        ce.add('force_ament_cmake_configure', force_ament_cmake_configure)
        ce.add('ament_cmake_args', options.ament_cmake_args)
        return ce

    def on_build(self, context):
        # Regardless of dry-run, try to determine if CMake should be invoked
        should_run_configure = False
        if context.force_ament_cmake_configure:
            should_run_configure = True
        elif not makefile_exists_at(context.build_space) or \
                not cmakecache_exists_at(context.build_space):
            # If either the Makefile or the CMake cache does not exist
            # we must configure
            should_run_configure = True
        cached_ament_cmake_config = get_cached_config(context.build_space,
                                                      'ament_cmake_args')
        ament_cmake_config = {
            'ament_cmake_args': context.ament_cmake_args,
            'build_tests': context.build_tests,
            'symlink_install': context.symlink_install,
        }
        if ament_cmake_config != cached_ament_cmake_config:
            should_run_configure = True
            self.warn(
                "Running cmake because arguments have changed.")
        # Store the ament_cmake_args for next invocation
        set_cached_config(context.build_space, 'ament_cmake_args',
                          ament_cmake_config)
        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('build', context)
        # Execute the configure step
        # (either cmake or the cmake_check_build_system make target)
        if should_run_configure:
            cmake_args = [context.source_space]
            cmake_args += context.ament_cmake_args
            cmake_args += ["-DCMAKE_INSTALL_PREFIX=" + context.install_space]
            if context.build_tests:
                cmake_args += ["-DAMENT_ENABLE_TESTING=1"]
            if context.symlink_install:
                cmake_args += ['-DAMENT_CMAKE_SYMLINK_INSTALL=1']
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
        assert context.build_tests
        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('test', context)
        if not IS_WINDOWS:
            if has_make_target(context.build_space, 'test') or context.dry_run:
                yield BuildAction(prefix + [MAKE_EXECUTABLE, 'test'])
            else:
                self.warn("Could not run tests for 'ament_cmake' package because it has no "
                          "'test' target")
        else:
            if MSBUILD_EXECUTABLE is None:
                raise VerbExecutionError("Could not find 'msbuild' executable")
            run_tests_project_file = project_file_exists_at(context.build_space, 'RUN_TESTS')
            if run_tests_project_file is not None or context.dry_run:
                yield BuildAction(prefix + [MSBUILD_EXECUTABLE, run_tests_project_file])
            else:
                self.warn("Could not find Visual Studio project file 'RUN_TESTS.vcxproj'")

    def on_install(self, context):
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
            (AmentCmakeBuildType.build_type, name))
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
            'export CMAKE_PREFIX_PATH=$CMAKE_PREFIX_PATH:$AMENT_PREFIX_PATH')

        generated_file = os.path.join(
            context.build_space, '%s__%s.sh' %
            (AmentCmakeBuildType.build_type, name))
        with open(generated_file, 'w') as h:
            for line in lines:
                h.write('%s\n' % line)

        return ['.', generated_file, '&&']
