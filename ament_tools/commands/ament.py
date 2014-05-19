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

from pkg_resources import iter_entry_points
import sys

from . import AMENT_COMMANDS_ENTRY_POINT


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    commands = {}
    for entry_point in iter_entry_points(group=AMENT_COMMANDS_ENTRY_POINT):
        commands[entry_point.name] = entry_point.load()

    if len(args) == 0 or \
            (len(args) == 1 and args[0] in ['help', '-h', '--help']) or \
            args[0] not in commands.keys():
        print('usage: ament <command>')
        print('')
        print('The available commands are:')
        max_length = max([len(name) for name in commands.keys()])
        for name, data in commands.items():
            print('  %s %s' % (name.ljust(max_length), data['description']))
        return

    commands[args[0]]['main'](args[1:])
