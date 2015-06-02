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

from ament_tools.context import ContextExtender

from ament_tools.helper import extract_argument_group

from ament_tools.build_types.cmake_common import cmakecache_exists_at
from ament_tools.build_types.cmake_common import makefile_exists_at

from ament_tools.build_types.cmake import CmakeBuildType

from ament_tools.build_types.common import get_cached_config
from ament_tools.build_types.common import set_cached_config

IS_WINDOWS = os.name == 'nt'


class AmentCmakeBuildType(CmakeBuildType):
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
            help="Arbitrary arguments which are passed to 'ament_cmake' CMake projects. "
                 "Argument collection can be terminated with '--'.")

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
        if getattr(options, 'force_configure', False):
            force_ament_cmake_configure = True
        ce.add('force_ament_cmake_configure', force_ament_cmake_configure)
        ce.add('ament_cmake_args', options.ament_cmake_args)
        return ce

    def on_build(self, context):
        # Regardless of dry-run, try to determine if CMake should be invoked
        should_run_configure = False
        if context.force_ament_cmake_configure or context.force_cmake_configure:
            should_run_configure = True
        elif not makefile_exists_at(context.build_space) or \
                not cmakecache_exists_at(context.build_space):
            # If either the Makefile or the CMake cache does not exist
            # we must configure
            should_run_configure = True
        cached_ament_cmake_config = get_cached_config(context.build_space,
                                                      'ament_cmake_args')
        ament_cmake_config = {
            'cmake_args': context.cmake_args,
            'ament_cmake_args': context.ament_cmake_args,
            'build_tests': context.build_tests,
            'symlink_install': context.symlink_install,
        }
        if ament_cmake_config != cached_ament_cmake_config:
            should_run_configure = True
            self.warn("Running cmake because arguments have changed.")
        # Store the ament_cmake_args for next invocation
        set_cached_config(context.build_space, 'ament_cmake_args',
                          ament_cmake_config)
        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('build', context)
        # Calculate any extra cmake args which are not common between cmake build types
        extra_cmake_args = []
        if should_run_configure:
            if context.build_tests:
                extra_cmake_args += ["-DAMENT_ENABLE_TESTING=1"]
            if context.symlink_install:
                extra_cmake_args += ['-DAMENT_CMAKE_SYMLINK_INSTALL=1']
            extra_cmake_args += context.cmake_args
            extra_cmake_args += context.ament_cmake_args
        # Yield the cmake common on_build (defined in CmakeBuildType)
        for step in self._common_cmake_on_build(
            should_run_configure, context, prefix, extra_cmake_args
        ):
            yield step

    def on_test(self, context):
        # Call cmake common on_test (defined in CmakeBuildType)
        for step in self._common_cmake_on_test(context, 'ament_cmake'):
            yield step

    def on_install(self, context):
        # Call cmake common on_install (defined in CmakeBuildType)
        for step in self._common_cmake_on_install(context):
            yield step
