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

from ament_tools import context


def test_context():
    c = context.Context()
    c.foo = 'bar'
    assert c.foo == 'bar'
    assert c['foo'] == 'bar'
    c['ping'] = 'pong'
    assert c.ping == 'pong'
    assert c['ping'] == 'pong'
    assert sorted(c.keys()) == sorted(['foo', 'ping'])
