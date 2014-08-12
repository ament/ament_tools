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

from ament_tools.build_types.cmake_common import has_make_target
from ament_tools.build_types.cmake_common import makefile_exists_at
from ament_tools.build_types.cmake_common import CMAKE_EXECUTABLE
from ament_tools.build_types.cmake_common import MAKE_EXECUTABLE

from ament_tools.build_types.common import extract_argument_group
from ament_tools.build_types.common import get_cached_config
from ament_tools.build_types.common import set_cached_config


class AmentCmakeBuildType(BuildType):
    build_type = 'ament_cmake'
    description = "ament package built with cmake"

    supports_symbolic_link_install = False

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

    def get_command_prefix(self, context):
        prefix = []
        local_setup = os.path.join(context.install_space, 'local_setup.sh')
        if os.path.isfile(local_setup):
            prefix = ['.', local_setup, '&&']
        return prefix

    def on_build(self, context):
        # Reguardless of dry-run, try to determine if CMake should be invoked
        should_run_configure = False
        if context.force_ament_cmake_configure:
            should_run_configure = True
        elif not makefile_exists_at(context.build_space):
            # If the Makefile does not exist, we must configure
            should_run_configure = True
        cached_ament_cmake_config = get_cached_config(context.build_space,
                                                      'ament_cmake_args')
        ament_cmake_config = {
            'ament_cmake_args': context.ament_cmake_args,
            'testing': context.testing,
        }
        if ament_cmake_config != cached_ament_cmake_config:
            should_run_configure = True
            self.warn(
                "Running cmake because arguments have changed.")
        # Store the ament_cmake_args for next invocation
        set_cached_config(context.build_space, 'ament_cmake_args',
                          ament_cmake_config)
        # Figure out if there is a setup file to source
        prefix = self.get_command_prefix(context)
        # Execute the configure step
        # (either cmake or the cmake_check_build_system make target)
        if should_run_configure:
            cmake_args = [context.source_space]
            cmake_args += context.ament_cmake_args
            cmake_args += ["-DCMAKE_INSTALL_PREFIX=" + context.install_space]
            if context.testing:
                cmake_args += ["-DAMENT_ENABLE_TESTING=1"]
            yield BuildAction(prefix + [CMAKE_EXECUTABLE] + cmake_args)
        else:
            yield BuildAction(prefix + [MAKE_EXECUTABLE, 'cmake_check_build_system'])
        # Now execute the build step
        yield BuildAction(prefix + [MAKE_EXECUTABLE] + context.make_flags)

    def on_test(self, context):
        assert context.testing
        # Figure out if there is a setup file to source
        prefix = self.get_command_prefix(context)
        if has_make_target(context.build_space, 'test') or context.dry_run:
            yield BuildAction(prefix + [MAKE_EXECUTABLE, 'test'])
        else:
            self.warn("Could not run test for ament_cmake package because it "
                      "has no 'test' target")

    def on_install(self, context):
        # TODO: Check for, and act on, the symbolic install option

        # Figure out if there is a setup file to source
        prefix = self.get_command_prefix(context)

        # Assumption: install target exists
        yield BuildAction(prefix + [MAKE_EXECUTABLE, 'install'])
