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

from __future__ import print_function

from ament_tools.verbs.build import prepare_arguments \
    as build_prepare_arguments
from ament_tools.verbs.build.cli import main as build_main
from ament_tools.verbs.test_pkg import main as test_pkg_main


def prepare_arguments(parser, args):
    """Add parameters to argparse for the build_pkg verb and its plugins.

    After adding the generic verb arguments, this function tries to determine
    the build type of the target package. This is done by gracefully trying
    to get the positional ``path`` argument from the arguments, falling back
    to the default ``os.curdir``. Then it searches for a package manifest in
    that path. If it finds the package manifest it then determines the build
    type of the package, e.g. ``ament_cmake``. It then trys to load a build
    type plugin for that build type. If the loading is successful it will allow
    the plugin to add additional arguments to the parser in a new
    :py:class:`argparse.ArgumentGroup` for that build type.

    :param parser: ArgumentParser object to which arguments are added
    :type parser: :py:class:`argparse.ArgumentParser`
    :param list args: list of arguments as str's
    :returns: modified version of the original parser given
    :rtype: :py:class:`argparse.ArgumentParser`
    """
    parser = build_prepare_arguments(parser, args)
    parser.add_argument(
        '--abort-on-test-error',
        action='store_true',
        default=False,
        help='Stop after tests with errors or failures',
    )
    return parser


def main(opts):
    rc_storage = {}

    def test_pkg_main_wrapper(opts):
        rc = test_pkg_main(opts)
        if rc:
            rc_storage['rc'] = rc
            if opts.abort_on_test_error:
                return rc
        return 0

    build_main(opts, test_pkg_main_wrapper)

    if 'rc' in rc_storage:
        return rc_storage['rc']
