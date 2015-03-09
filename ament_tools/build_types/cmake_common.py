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

import os
import re
import subprocess

from osrf_pycommon.process_utils import which

CMAKE_EXECUTABLE = which('cmake')
MAKE_EXECUTABLE = which('make')
MSBUILD_EXECUTABLE = which('msbuild')

__target_re = re.compile(r'^([a-zA-Z0-9][a-zA-Z0-9_\.]*):')


def has_make_target(path, target):
    global __target_re
    output = subprocess.check_output([MAKE_EXECUTABLE, '-pn'], cwd=path)
    lines = output.decode().splitlines()
    targets = [m.group(1) for m in [__target_re.match(l) for l in lines] if m]
    return target in targets


def cmakecache_exists_at(path):
    cmakecache = os.path.join(path, 'CMakeCache.txt')
    return os.path.isfile(cmakecache)


def makefile_exists_at(path):
    makefile = os.path.join(path, 'Makefile')
    return os.path.isfile(makefile)


def solution_file_exists_at(path, package_name):
    solution_file = os.path.join(path, package_name + '.sln')
    if not os.path.isfile(solution_file):
        return None
    return solution_file


def project_file_exists_at(path, target):
    project_file = os.path.join(path, target + '.vcxproj')
    if not os.path.isfile(project_file):
        return None
    return project_file
