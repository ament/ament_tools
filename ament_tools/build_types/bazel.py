# Copyright 2017 Open Source Robotics Foundation, Inc.
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

import subprocess

from ament_tools.build_type import BuildAction
from ament_tools.build_type import BuildType

from ament_tools.context import ContextExtender

from ament_tools.helper import extract_argument_group

from osrf_pycommon.process_utils import which

BAZEL_EXECUTABLE = which('bazel')


def _has_target(path, target):
    # To query bazel for a list of all labels, we use:
    # bazel query '//...' --output=label
    cmd = [BAZEL_EXECUTABLE, 'query', '//...', '--output=label']
    output = subprocess.check_output(cmd, cwd=path)
    lines = output.decode().splitlines()
    # Each line in the output starts with a double slash, followed by
    # either a colon and a target name, or a package name.  We look to see
    # if the requested target exists.
    return target in lines


class BazelBuildType(BuildType):
    build_type = 'bazel'
    description = 'bazel project'

    def prepare_arguments(self, parser):
        parser.add_argument(
            '--bazel-args',
            nargs='*',
            default=[],
            help='Arbitrary arguments which are passed to all bazel projects. '
            "Argument collection can be terminated with '--'.")

    def argument_preprocessor(self, args):
        args, bazel_args = extract_argument_group(args, '--bazel-args')
        extras = {
            'bazel_args': bazel_args,
        }
        return args, extras

    def extend_context(self, options):
        ce = ContextExtender()
        ce.add('bazel_args', getattr(options, 'bazel_args', []))
        return ce

    def on_build(self, context):
        cmd = [BAZEL_EXECUTABLE, 'build'] + context.bazel_args + ['//...']
        yield BuildAction(cmd, cwd=context.source_space)

    def on_install(self, context):
        # clalancette: Note that bazel has no real concept of an install
        # target.  Thus, we define a de-facto one here which is a run
        # command with a target of //:install.
        if _has_target(context.source_space, '//:install'):
            cmd = [BAZEL_EXECUTABLE, 'run'] + context.bazel_args + \
                ['//:install', context.install_space]
            yield BuildAction(cmd, cwd=context.source_space)
        else:
            self.warn("Could not install package '{0}' because it has no "
                      "'//:install' target".format(context.package_manifest.name))

    def on_uninstall(self, context):
        # clalancette: Note that bazel has no real concept of an install
        # target.  Thus, we define a de-facto one here which is a run
        # command with a target of //:uninstall.
        if _has_target(context.source_space, '//:uninstall'):
            cmd = [BAZEL_EXECUTABLE, 'run'] + context.bazel_args + \
                ['//:uninstall', context.install_space]
            yield BuildAction(cmd, cwd=context.source_space)
        else:
            self.warn("Could not uninstall package '{0}' because it has no "
                      "'//:uninstall' target".format(context.package_manifest.name))

    def on_test(self, context):
        cmd = [BAZEL_EXECUTABLE, 'test'] + context.bazel_args + ['//...']
        yield BuildAction(cmd, cwd=context.source_space)
