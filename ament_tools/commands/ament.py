from ament_tools.commands import AMENT_COMMANDS_ENTRY_POINT
from pkg_resources import iter_entry_points
import sys


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
