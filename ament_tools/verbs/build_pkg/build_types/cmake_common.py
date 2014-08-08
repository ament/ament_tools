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

from osrf_pycommon.process_utils import which

CMAKE_EXECUTABLE = which('cmake')
MAKE_EXECUTABLE = which('make')


def makefile_exists_at(path):
    makefile = os.path.join(path, 'Makefile')
    return os.path.exists(makefile)
