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

import pkg_resources

AMENT_BUILD_TYPES_ENTRY_POINT = 'ament.build_types'


def yield_supported_build_types(name=None):
    return pkg_resources.iter_entry_points(
        group=AMENT_BUILD_TYPES_ENTRY_POINT,
        name=name,
    )


class MissingPluginError(Exception):
    pass


def get_class_for_build_type(build_type):
    """
    Get the class for a given package build type.

    :param str build_type: name of build_type plugin, e.g. 'ament_cmake'
    :returns: class for the requirest build_type plugin
    :raises: RuntimeError if there are more than one plugins for a requested
        build type.
    :raises: MissingPluginError if there is no plugin for the requested
        build type.
    """
    entry_points = list(yield_supported_build_types(build_type))
    if len(entry_points) > 1:
        # Shouldn't happen, defensive
        raise RuntimeError('More than one build_type entry_point.')
    if len(entry_points) == 0:
        raise MissingPluginError(
            "No plugin to handle a package with build_type '{0}'"
            .format(build_type))
    return entry_points[0].load()
