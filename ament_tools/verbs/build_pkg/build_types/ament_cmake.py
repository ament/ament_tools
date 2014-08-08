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

from ament_tools.build_type import BuildAction
from ament_tools.build_type import BuildType

from ament_tools.context import ContextExtender

from .cmake_common import makefile_exists_at
from .cmake_common import CMAKE_EXECUTABLE
from .cmake_common import MAKE_EXECUTABLE

from .common import get_cached_config
from .common import set_cached_config


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

    def on_build(self, context):
        # Reguardless of dry-run, try to determine if CMake should be invoked
        should_run_configure = False
        if context.force_ament_cmake_configure:
            should_run_configure = True
        elif not makefile_exists_at(context.build_space):
            # If the Makefile does not exist, we must configure
            should_run_configure = True
        cached_ament_cmake_args = get_cached_config(context.build_space,
                                                    'ament_cmake_args')
        if context.ament_cmake_args != cached_ament_cmake_args:
            should_run_configure = True
            self.warn("Running cmake because 'ament cmake args' have changed.")
        # Store the ament_cmake_args for next invocation
        set_cached_config(context.build_space, 'ament_cmake_args',
                          context.ament_cmake_args)
        # Execute the configure step
        # (either cmake or the cmake_check_build_system make target)
        if should_run_configure:
            cmake_args = [context.source_space]
            cmake_args += context.ament_cmake_args
            cmake_args += ["-DCMAKE_INSTALL_PREFIX=" + context.install_space]
            yield BuildAction([CMAKE_EXECUTABLE] + cmake_args)
        else:
            yield BuildAction([MAKE_EXECUTABLE, 'cmake_check_build_system'])
        # Now execute the build step
        yield BuildAction([MAKE_EXECUTABLE] + context.make_flags)

    def on_install(self, context):
        # TODO: Check for, and act on, the symbolic install option
        yield BuildAction([MAKE_EXECUTABLE, 'install'])


def extract_argument_group(args, delimiting_option):
    if delimiting_option not in args:
        return args, []
    index = args.index(delimiting_option)
    return args[0:index], args[index + 1:]
