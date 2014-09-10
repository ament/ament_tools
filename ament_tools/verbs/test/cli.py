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

import os

from ament_tools.verbs.test_pkg import main as test_pkg_main
from ament_tools.topological_order import topological_order
from ament_tools.verbs.build_pkg import TestError


def main(options):
    packages = topological_order(options.basepath)

    print('')
    print('# Topological order')
    start_with_found = not options.start_with
    for (path, package) in packages:
        if package.name == options.start_with:
            start_with_found = True
        if not start_with_found:
            print(' skip %s' % package.name)
        else:
            print(' - %s' % package.name)
    print('')

    any_test_errors = False
    start_with_found = not options.start_with
    for (path, package) in packages:
        if package.name == options.start_with:
            start_with_found = True
        if not start_with_found:
            print('# Skipping: %s' % package.name)
            continue
        pkg_path = os.path.join(options.basepath, path)

        print('')
        print('# Testing: %s' % package.name)
        print('')
        options.path = pkg_path
        try:
            rc = test_pkg_main(options)
        except TestError as e:
            if options.abort_test_error:
                return str(e)
            rc = None
            any_test_errors = True
        if rc:
            return rc

    if any_test_errors:
        return 1
