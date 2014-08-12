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


def main(options):
    packages = topological_order(options.basepath)

    print('')
    print('# Topologoical order')
    for (path, package) in packages:
        print(' - %s' % package.name)
    print('')

    for (path, package) in packages:
        pkg_path = os.path.join(options.basepath, path)

        print('')
        print('# Testing: %s' % package.name)
        print('')
        options.path = pkg_path
        rc = test_pkg_main(options)
        if rc:
            return rc
