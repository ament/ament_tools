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
from ament_tools.verbs.test_pkg import prepare_arguments \
    as test_pkg_prepare_arguments


def prepare_arguments(parser, args):
    """Add parameters to argparse for the test verb and its plugins.

    :param parser: ArgumentParser object to which arguments are added
    :type parser: :py:class:`argparse.ArgumentParser`
    :param list args: list of arguments as str's
    :returns: modified version of the original parser given
    :rtype: :py:class:`argparse.ArgumentParser`
    """
    parser = build_prepare_arguments(parser, args)
    test_pkg_prepare_arguments(parser, args, skip_build_pkg_arguments=True)
    parser.add_argument(
        '--abort-on-test-error',
        action='store_true',
        default=False,
        help='Abort after a package with test errors or failures',
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
