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

import argparse
import os
import re

from multiprocessing import cpu_count

from ament_package import package_exists_at
from ament_package import PACKAGE_MANIFEST_FILENAME


def argparse_existing_dir(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError("Path '%s' does not exist" % path)
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError("Path '%s' is not a directory" % path)
    return path


def argparse_existing_package(path):
    path = argparse_existing_dir(path)
    if not package_exists_at(path):
        raise argparse.ArgumentTypeError(
            "Path '%s' does not contain a '%s' file" %
            (path, PACKAGE_MANIFEST_FILENAME))
    return path


def determine_path_argument(cwd, base_path, argument, default):
    if argument is None:
        # if no argument is passed the default is relative to the base_path
        return os.path.join(base_path, default)
    # if an argument is passed it is relative to cwd (or absolute)
    return os.path.abspath(os.path.join(cwd, argument))


def extract_jobs_flags(arguments):
    """Extracts make job flags from a list of other make flags, i.e. -j8 -l8

    :param arguments: string of space separated arguments which may or may not
        contain make job flags
    :type arguments: str
    :returns: list of make jobs flags as a space separated string
    :rtype: str
    """
    regex = (
        r'(?:^|\s)(-?(?:j|l)(?:\s*[0-9]+|\s|$))'
        r'|'
        r'(?:^|\s)((?:--)?(?:jobs|load-average)(?:(?:=|\s+)[0-9]+|(?:\s|$)))'
    )
    matches = re.findall(regex, arguments) or []
    matches = [m[0] or m[1] for m in matches]
    return ' '.join([m.strip() for m in matches]) if matches else None


def combine_make_flags(make_flags, args, extras):
    """Combine make flags and arg's make job flags with make_flags in extras.

    :param list make_flags: existing make_flags, extracted from args already.
    :param list args: command line args with ``--make-flags ...`` extracted.
    :param dict extras: extras dict to which make flags are added/extended.
    """
    # Add make_flags in extras, if they exist, to verb's --make-flags
    make_flags += extras.get('make_flags', [])

    # Extract make job arguments from main arguments and add to make_flags
    make_job_flags = extract_jobs_flags(' '.join(args))
    if make_job_flags:
        args = re.sub(make_job_flags, '', ' '.join(args)).split()
        make_flags.extend(make_job_flags.split())

    # Ensure make args will have job flags and then store make_flags in extras
    extras['make_flags'] = ensure_make_job_flags(make_flags)


def ensure_make_job_flags(input_make_args):
    """Ensures that make will get correct job flags, either from args or env.

    If no job flags are present and there are none in the MAKEFLAGS environment
    variable, then make flags are set to the cpu_count, e.g. -j4 -l4.

    :param input_make_args: list of make arguments to be handled
    :type input_make_args: list
    :returns: copied list of make arguments, potentially with modifications
    :rtype: list
    """
    make_args = list(input_make_args)

    # If no -j/--jobs/-l/--load-average flags are in make_args
    if not extract_jobs_flags(' '.join(make_args)):
        # If -j/--jobs/-l/--load-average are in MAKEFLAGS
        if extract_jobs_flags(os.environ.get('MAKEFLAGS', "")):
            # Do not extend make arguments, let MAKEFLAGS set things
            pass
        else:
            # Else extend the make_arguments to include some jobs flags
            # Use the number of CPU cores
            try:
                jobs = cpu_count()
                make_args.append('-j{0}'.format(jobs))
                make_args.append('-l{0}'.format(jobs))
            except NotImplementedError:
                # If the number of cores cannot be determined,
                # then do not extend args
                pass
    return make_args


def extract_argument_group(args, delimiting_option):
    """Extract a group of arguments from a list of arguments using a delimeter.

    Here is an example:

    .. code-block:: python

        >>> extract_argument_group(['foo', '--args', 'bar', '--baz'], '--args')
        (['--foo'], ['bar', '--baz'])

    :param list args: list of strings which are ordered arguments.
    :param str delimiting_option: option which denotes where to split the args.
    :returns: tuple of arguments before and after the delimeter.
    :rtype: tuple
    """
    if delimiting_option not in args:
        return args, []
    index = args.index(delimiting_option)
    return args[0:index], args[index + 1:]
