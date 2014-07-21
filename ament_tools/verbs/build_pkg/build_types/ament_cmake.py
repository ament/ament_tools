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

import multiprocessing
import os
import re
import subprocess
import sys

from ament_tools.verbs.build_pkg import run_command


def argument_preprocessor(args):
    """Process the args for the build verb, before being passed to argparse"""
    # CMake/make pass-through flags collect dashed options. They require special
    # handling or argparse will complain about unrecognized options.
    args = sys.argv[1:] if args is None else args
    args, cmake_args, make_args = extract_cmake_and_make_arguments(args)
    # Extract make jobs flags.
    jobs_flags = extract_jobs_flags(' '.join(args))
    if jobs_flags:
        args = re.sub(jobs_flags, '', ' '.join(args)).split()
        jobs_flags = jobs_flags.split()
    extras = {
        'cmake_args': cmake_args,
        'make_args': make_args + (jobs_flags or []),
    }
    return args, extras


def cmake_input_changed(build_prefix, cmake_args=None, filename='cmake_args'):
    # get current input
    cmake_args = ' '.join(cmake_args) if cmake_args else ''

    # file to store current input
    changed = False
    input_filename = os.path.join(build_prefix, '%s.cache' % filename)
    if not os.path.exists(input_filename):
        changed = True
    else:
        # compare with previously stored input
        with open(input_filename, 'r') as f:
            previous_cmake_args = f.readline().rstrip()
        if cmake_args != previous_cmake_args:
            changed = True

    # store current input for next invocation
    with open(input_filename, 'w') as f:
        f.write(cmake_args)

    return changed


def extract_cmake_and_make_arguments(args):
    cmake_args = []
    make_args = []

    arg_types = {
        '--cmake-args': cmake_args,
        '--make-args': make_args
    }

    arg_indexes = {}
    for k in arg_types.keys():
        if k in args:
            arg_indexes[args.index(k)] = k

    def split_arguments(args, splitter_name, default=None):
        if splitter_name not in args:
            return args, default
        index = args.index(splitter_name)
        return args[0:index], args[index + 1:]

    for index in reversed(sorted(arg_indexes.keys())):
        arg_type = arg_indexes[index]
        args, specific_args = split_arguments(args, arg_type)
        arg_types[arg_type].extend(specific_args)

    return args, cmake_args, make_args


def extract_jobs_flags(mflags):
    regex = r'(?:^|\s)(-?(?:j|l)(?:\s*[0-9]+|\s|$))' + \
            r'|' + \
            r'(?:^|\s)((?:--)?(?:jobs|load-average)' + \
            r'(?:(?:=|\s+)[0-9]+|(?:\s|$)))'
    matches = re.findall(regex, mflags) or []
    matches = [m[0] or m[1] for m in matches]
    return ' '.join([m.strip() for m in matches]) if matches else None


def handle_make_arguments(input_make_args):
    make_args = list(input_make_args)

    # if no -j/--jobs/-l/--load-average flags are in make_args
    if not extract_jobs_flags(' '.join(make_args)):
        # if -j/--jobs/-l/--load-average are in MAKEFLAGS
        if 'MAKEFLAGS' in os.environ and \
                extract_jobs_flags(os.environ['MAKEFLAGS']):
            # do not extend make arguments, let MAKEFLAGS set things
            pass
        else:
            # else extend the make_arguments to include some jobs flags
            # use the number of CPU cores
            try:
                jobs = multiprocessing.cpu_count()
                make_args.append('-j{0}'.format(jobs))
                make_args.append('-l{0}'.format(jobs))
            except NotImplementedError:
                # the number of cores cannot be determined, do not extend args
                pass
    return make_args


def prepare_arguments(parser):
    parser.add_argument(
        '--force-cmake',
        action='store_true',
        help="Invoke 'cmake' even if it has been executed before")
    parser.add_argument(
        '--cmake-args',
        nargs='*',
        default=[],
        help='Arbitrary arguments which are passed to CMake. '
             'It must be passed after other arguments since it collects all '
             'following options.')
    parser.add_argument(
        '--make-args',
        nargs='*',
        default=[],
        help='Arbitrary arguments which are passed to make. '
             'It must be passed after other arguments since it collects all '
             'following options.')


def main(opts):
    pkg_path = os.path.abspath(opts.path)
    build_prefix = os.path.abspath(opts.build_prefix)
    install_prefix = os.path.abspath(opts.install_prefix)

    if not os.path.exists(build_prefix):
        os.makedirs(build_prefix)

    try:
        # consider invoking cmake
        makefile = os.path.join(build_prefix, 'Makefile')
        if not os.path.exists(makefile) or \
                opts.force_cmake or \
                cmake_input_changed(build_prefix, opts.cmake_args):
            cmd = [
                'cmake',
                pkg_path,
                '-DCMAKE_INSTALL_PREFIX=%s' % install_prefix,
            ]
            cmd += opts.cmake_args
            run_command(cmd, cwd=build_prefix)

        # invoke make
        cmd = [
            'make',
        ]
        cmd += opts.make_args
        run_command(cmd, cwd=build_prefix)

        # invoke make install
        cmd = [
            'make',
            'install',
        ]
        cmd += handle_make_arguments(opts.make_args)
        run_command(cmd, cwd=build_prefix)
    except subprocess.CalledProcessError:
        return 1

entry_point_data = dict(
    build_type='ament_cmake',
    description='ament package built with cmake',
    main=main,
    prepare_arguments=prepare_arguments,
    argument_preprocessor=argument_preprocessor,
)
