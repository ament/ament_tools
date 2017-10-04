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

from ament_package.dependency import Dependency
from ament_package.export import Export
from ament_package.package import Package

__all__ = ('entry_point_data')


def package_exists_at(path):
    return os.path.exists(os.path.join(path, 'CMakeLists.txt'))


def parse_package(path):
    if not package_exists_at(path):
        return None
    cmakelists = os.path.join(path, 'CMakeLists.txt')
    data = extract_data(cmakelists)
    pkg = Package(filename=cmakelists, **data)
    pkg.exports = [Export('build_type', content='cmake')]
    return pkg


def extract_data(cmakelists):
    with open(cmakelists, 'r') as h:
        content = h.read()
    content = remove_cmake_comments(content)

    data = {}
    data['name'] = extract_project_name(content)
    if not data['name']:
        raise RuntimeError("Failed to extract project name from '%s'" % cmakelists)

    build_depends = extract_build_dependencies(content)
    data['build_depends'] = [Dependency(name) for name in build_depends]

    return data


def remove_cmake_comments(content):
    lines = content.splitlines()
    for index, line in enumerate(lines):
        lines[index] = remove_cmake_comments_from_line(line)
    return '\n'.join(lines)


def remove_cmake_comments_from_line(line):
    # match coments starting with # which are not within a string enclosed in double quotes
    # strings:  vvvvvvvvv
    # comments:           vvvvv
    # other:                    vvvvvvvv
    pattern = r'("[^"]*")|(#.*)|([^#"]*)'

    modline = ''
    for matches in re.findall(pattern, line):
        modline += matches[0] + matches[2]
    return modline


def extract_project_name(content):
    # extract project name
    # keyword:          vvvvvvv
    # optional whitespaces:    vvv  vvv                      vvv
    # parenthesis:                vv                                    vv
    # optional quotes:                 vvvv               vv
    # project name:                        vvvvvvvvvvvvvvv
    # optional languages:                                       vvvvvvvv
    match = re.search(r'project\s*\(\s*("?)([a-zA-Z0-9_]+)\1(\s+[^\)]*)?\)', content,
                      re.IGNORECASE)
    if not match:
        return None
    return match.group(2)


def extract_build_dependencies(content):
    # extract found packages
    # keyword:             vvvvvvvvvvvv
    # optional whitespaces:            vvv  vvv                      vvv
    # parenthesis:                        vv                                    vv
    # optional quotes:                         vvvv               vv
    # package name:                                vvvvvvvvvvvvvvv
    # optional arguments:                                               vvvvvvvv
    matches = re.findall(r'find_package\s*\(\s*("?)([a-zA-Z0-9_]+)\1(\s+[^\)]*)?\)', content,
                         re.IGNORECASE)
    return [m[1] for m in matches]


# meta information of the entry point
entry_point_data = {
    'name': 'cmake',
    'description': "A package containing a 'CMakeLists.txt' file.",
    'package_exists_at': package_exists_at,
    'parse_package': parse_package,
    # other package types must be checked before
    # since they might also contain a CMakeLists.txt file
    'depends': ['ament'],
}
