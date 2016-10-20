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

import sys

from ament_tools.build_type_discovery import get_class_for_build_type

from ament_tools.verbs.build_pkg import prepare_arguments \
    as build_pkg_prepare_arguments
from ament_tools.verbs.build_pkg.cli import get_build_type
from ament_tools.verbs.build_pkg.cli import handle_build_action
from ament_tools.verbs.build_pkg.cli import get_context as build_pkg_get_context
from ament_tools.verbs.build_pkg.cli import run as build_pkg_run


def prepare_arguments(parser, args, skip_build_pkg_arguments=False):
    """
    Add parameters to argparse for the test_pkg verb and its plugins.

    :param parser: ArgumentParser object to which arguments are added
    :type parser: :py:class:`argparse.ArgumentParser`
    :param list args: list of arguments as str's
    :returns: modified version of the original parser given
    :rtype: :py:class:`argparse.ArgumentParser`
    """
    if not skip_build_pkg_arguments:
        parser = build_pkg_prepare_arguments(parser, args)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--retest-until-fail',
        type=int, default=0, metavar='N',
        help='Rerun tests up to N times if they pass',
    )
    group.add_argument(
        '--retest-until-pass',
        type=int, default=0, metavar='N',
        help='Rerun failing tests up to N times',
    )
    return parser


def main(opts):
    opts.build_tests = True
    context = build_pkg_get_context(opts)
    context.retest_until_pass = (opts.retest_until_pass > 0)
    rc = build_pkg_run(opts, context)
    if rc:
        return rc

    # Load up build type plugin class
    build_type = get_build_type(opts.path)
    build_type_impl = get_class_for_build_type(build_type)()

    # Run the test command
    pkg_name = context.package_manifest.name
    print("+++ Testing '{0}'".format(pkg_name))
    context.test_iteration = 0
    while True:
        try:
            on_test_ret = build_type_impl.on_test(context)
        except (AttributeError, NotImplementedError):
            print("on_test() is not implemented for build type '%s'" %
                  build_type, file=sys.stderr)
            return
        try:
            handle_build_action(on_test_ret, context)
        except SystemExit:
            # check if tests should be rerun
            if opts.retest_until_pass > context.test_iteration:
                context.test_iteration += 1
                print("+++ Testing '%s' again (retry #%d of %d)" %
                      (pkg_name, context.test_iteration, opts.retest_until_pass))
                continue
            # there is no way to distinguish why the test returned non zero
            # the test invocation itself could have failed:
            # return e.code
            # but it could have also run successful and only failed some tests:
            return
        # check if tests should be rerun
        if opts.retest_until_fail > context.test_iteration:
            context.test_iteration += 1
            print("+++ Testing '%s' again (retry #%d of %d)" %
                  (pkg_name, context.test_iteration, opts.retest_until_fail))
            continue
        break
