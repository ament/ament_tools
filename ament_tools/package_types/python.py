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
import distutils.core
import re
try:
    import setuptools
except ImportError:
    pass

from ament_package.dependency import Dependency
from ament_package.export import Export
from ament_package.package import Package

__all__ = ['entry_point_data']


def package_exists_at(path):
    return os.path.exists(os.path.join(path, 'setup.py'))


def parse_package(path):
    if not package_exists_at(path):
        return None
    setuppy = os.path.join(path, 'setup.py')
    data = extract_data(setuppy)
    pkg = Package(filename=setuppy, **data)
    pkg.exports = [Export('build_type', content='ament_python')]
    return pkg


def extract_data(setuppy):
    # be sure you're in the directory containing
    # setup.py so the sys.path manipulation works,
    # so the import of __version__ works
    old_cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.abspath(setuppy)))
    try:
        data = {'name': 'unknown'}
        fake_setup = create_mock_setup_function(data)
        # patch setup() function of distutils and setuptools for the
        # context of evaluating setup.py
        try:
            distutils_backup = distutils.core.setup
            distutils.core.setup = fake_setup
            try:
                setuptools_backup = setuptools.setup
                setuptools.setup = fake_setup
            except NameError:
                pass

            with open('setup.py', 'r') as h:
                exec(h.read())
        finally:
            distutils.core.setup = distutils_backup
            try:
                setuptools.setup = setuptools_backup
            except NameError:
                pass
        return data

    finally:
        os.chdir(old_cwd)


def create_mock_setup_function(data):
    """
    Create a setup function mock to capture its arguments.

    It can replace either distutils.core.setup or setuptools.setup.

    :param data: a dictionary which is updated with the captured arguments
    :returns: a function to replace disutils.core.setup and setuptools.setup
    """
    def setup(*args, **kwargs):
        if 'name' not in kwargs:
            raise RuntimeError(
                "setup() function invoked without the keyword argument 'name'")
        data['name'] = kwargs['name']

        if 'install_requires' in kwargs:
            data['build_depends'] = []
            for install_require in kwargs['install_requires']:
                # split of version specifiers
                name = re.split(r'<|>|<=|>=|==|!=', install_require)[0]
                # map from Python package name to ROS package name convention
                name = name.rstrip().replace('-', '_')
                data['build_depends'].append(Dependency(name))

    return setup


# meta information of the entry point
entry_point_data = dict(
    name='python',
    description="A package containing a 'setup.py' file.",
    package_exists_at=package_exists_at,
    parse_package=parse_package,
    # other package types must be checked before
    # since they might also contain a setup.py file
    depends=['ament', 'cmake'],
)
