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

import json
import os


def get_cached_config(build_space, name):
    path = os.path.join(build_space, '{name}.cache'.format(name=name))
    if not os.path.isfile(path):
        return None
    with open(path, 'r') as f:
        return json.loads(f.read())


def set_cached_config(build_space, name, value):
    if not os.path.isdir(build_space):
        assert not os.path.isfile(build_space), \
            ("build_space cannot be a file: {build_space}"
             .format(build_space=build_space))
        os.makedirs(build_space)
    path = os.path.join(build_space, '{name}.cache'.format(name=name))
    with open(path, 'w') as f:
        f.write(json.dumps(value, sort_keys=True))
