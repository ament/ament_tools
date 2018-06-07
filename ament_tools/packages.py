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

"""Library to find packages in the filesystem."""

import os

from ament_tools.package_types import package_exists_at
from ament_tools.package_types import parse_package


def find_package_paths(basepath, exclude_paths=None):
    """
    Crawl the filesystem to find package manifest files.

    When a subfolder contains a file ``AMENT_IGNORE`` it is ignored.

    :param str basepath: The path to search in
    :param list exclude_paths: A list of paths which should not be searched
    :returns: A list of relative paths containing package manifest files
    ``list``
    """
    paths = []
    real_exclude_paths = []
    if exclude_paths is not None:
        real_exclude_paths = [os.path.realpath(p) for p in exclude_paths]
    for dirpath, dirnames, filenames in os.walk(basepath, followlinks=True):
        real_dirpath = os.path.realpath(dirpath)
        if 'AMENT_IGNORE' in filenames or real_dirpath in real_exclude_paths:
            del dirnames[:]
            continue
        elif package_exists_at(dirpath):
            paths.append(os.path.relpath(dirpath, basepath))
            del dirnames[:]
            continue
        for dirname in dirnames:
            if dirname.startswith('.'):
                dirnames.remove(dirname)
    return paths


def find_packages(basepath, exclude_paths=None):
    """
    Crawl the filesystem to find package manifest files and parses them.

    :param str basepath: The path to search in
    :param list exclude_paths: A list of paths which should not be searched
    :returns: A dict mapping relative paths to
        :py:class:`catkin_pkg.package.Package` objects
    :rtype: dict
    """
    packages = {}
    package_paths = find_package_paths(basepath, exclude_paths=exclude_paths)
    for path in package_paths:
        packages[path] = parse_package(os.path.join(basepath, path))
    return packages


def find_unique_packages(basepath, exclude_paths=None):
    """
    Crawl the filesystem to find package manifest files and parses them.

    :param str basepath: The path to search in
    :param list exclude_paths: A list of paths which should not be searched
    :returns: A dict mapping relative paths to
        :py:class:`catkin_pkg.package.Package` objects
    :rtype: dict
    :raises: :exc:RuntimeError` If multiple packages have the same name
    """
    packages = find_packages(basepath, exclude_paths=exclude_paths)
    package_paths_by_name = {}
    for path, package in packages.items():
        if package.name not in package_paths_by_name:
            package_paths_by_name[package.name] = set()
        package_paths_by_name[package.name].add(path)
    duplicates = {name: paths
                  for name, paths in package_paths_by_name.items()
                  if len(paths) > 1}
    if duplicates:
        line_template = 'Multiple packages found with the same name "%s":\n%s'

        def paths_to_str(name):
            return '\n'.join(['- %s' % p for p in sorted(duplicates[name])])
        lines = [line_template % (name, paths_to_str(name))
                 for name in sorted(duplicates.keys())]
        raise RuntimeError('\n'.join(lines))
    return packages
