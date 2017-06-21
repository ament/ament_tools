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

from collections import Counter

import pkg_resources

AMENT_PACKAGE_TYPES_ENTRY_POINT = 'ament.package_types'


def package_exists_at(path):
    for package_type in get_package_types():
        if package_type['package_exists_at'](path):
            return True
    return False


def parse_package(path):
    for package_type in get_package_types():
        if package_type['package_exists_at'](path):
            pkg = package_type['parse_package'](path)
            return pkg
    raise RuntimeError("Failed to parse package in '%s'" % path)


_cached_package_types = None


def get_package_types(force_loading_entry_points=False):
    global _cached_package_types
    if _cached_package_types is None or force_loading_entry_points:
        entry_points = list(pkg_resources.iter_entry_points(group=AMENT_PACKAGE_TYPES_ENTRY_POINT))
        if not entry_points:
            raise RuntimeError('No package type entry points')
        entry_points_data = [ep.load() for ep in entry_points]

        # ensure unique names
        counter = Counter()
        counter.update([d['name'] for d in entry_points_data])
        most_common = counter.most_common(1)[0]
        if most_common[1] > 1:
            raise RuntimeError("Multiple package types with the same name '%s'" % most_common[0])

        # order topologically
        ordered = []
        by_name = {d['name']: [set(d['depends']), d] for d in entry_points_data}
        while by_name:
            for name in sorted(by_name.keys()):
                depends = by_name[name][0]
                # take first entry with no unsatisfied dependencies
                if not depends:
                    data = by_name[name][1]
                    ordered.append(data)
                    del by_name[name]
                    # remove name from dependency list of other entries
                    for v in by_name.values():
                        v[0].remove(name)
                    break
            else:
                raise RuntimeError(
                    'Failed to determine topological order of the following package types: ' +
                    (', '.join(sorted(by_name.keys()))))
        _cached_package_types = ordered

    return _cached_package_types
