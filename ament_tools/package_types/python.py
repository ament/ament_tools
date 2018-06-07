# Copyright 2015 Open Source Robotics Foundation, Inc.
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

import os
import re

from catkin_pkg.package import Dependency
from catkin_pkg.package import Export
from catkin_pkg.package import Package

from ament_tools.setup_arguments import get_setup_arguments

__all__ = ('entry_point_data')


def package_exists_at(path):
    return os.path.exists(os.path.join(path, 'setup.py'))


def parse_package(path):
    if not package_exists_at(path):
        return None
    setuppy = os.path.join(path, 'setup.py')
    kwargs = get_setup_arguments(setuppy)
    data = extract_data(**kwargs)
    pkg = Package(filename=setuppy, **data)
    pkg.exports = [Export('build_type', content='ament_python')]
    return pkg


def extract_data(**kwargs):
    if 'name' not in kwargs:
        raise RuntimeError(
            "setup() function invoked without the keyword argument 'name'")
    data = {'name': kwargs['name']}

    if 'install_requires' in kwargs:
        data['build_depends'] = []
        for install_require in kwargs['install_requires']:
            # split of version specifiers
            name = re.split(r'<|>|<=|>=|==|!=', install_require)[0]
            # map from Python package name to ROS package name convention
            name = name.rstrip().replace('-', '_')
            data['build_depends'].append(Dependency(name))
    return data


# meta information of the entry point
entry_point_data = {
    'name': 'python',
    'description': "A package containing a 'setup.py' file.",
    'package_exists_at': package_exists_at,
    'parse_package': parse_package,
    # other package types must be checked before
    # since they might also contain a setup.py file
    'depends': ['ament', 'cmake'],
}
