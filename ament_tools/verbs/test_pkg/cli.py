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

from __future__ import print_function

from ament_tools.build_type_discovery import get_class_for_build_type

from ament_tools.verbs.build_pkg import prepare_arguments \
    as build_pkg_prepare_arguments
from ament_tools.verbs.build_pkg.cli import create_context
from ament_tools.verbs.build_pkg.cli import get_build_type
from ament_tools.verbs.build_pkg.cli import handle_build_action
from ament_tools.verbs.build_pkg.cli import main as build_pkg_main


def main(opts):
    opts.build_tests = True
    rc = build_pkg_main(opts)
    if rc:
        return rc

    context = create_context(opts)

    # Load up build type plugin class
    build_type = get_build_type(opts.path)
    build_type_impl = get_class_for_build_type(build_type)()

    # Run the test command
    pkg_name = context.package_manifest.name
    print("+++ Testing '{0}'".format(pkg_name))
    on_test_ret = build_type_impl.on_test(context)
    try:
        handle_build_action(on_test_ret, context)
    except SystemExit as e:
        return 1
