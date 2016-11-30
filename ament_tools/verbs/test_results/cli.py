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

from __future__ import print_function

import os
import sys
import traceback
from xml.etree.ElementTree import ElementTree

from ament_tools.helper import argparse_existing_dir


def prepare_arguments(parser, args):
    """
    Add parameters to argparse for the build verb and available plugins.

    After adding the generic verb arguments, this function loads all available
    build_type plugins and then allows the plugins to add additional arguments
    to the parser in a new :py:class:`argparse.ArgumentGroup` for that
    build_type.

    :param parser: ArgumentParser object to which arguments are added
    :type parser: :py:class:`argparse.ArgumentParser`
    :param list args: list of arguments as str's
    :returns: modified version of the original parser given
    :rtype: :py:class:`argparse.ArgumentParser`
    """
    # Add verb arguments
    parser.add_argument(
        'basepath',
        nargs='?',
        type=argparse_existing_dir,
        default=os.curdir,
        help="Base path to start crawling for test results (default '.')",
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=False,
        help='Show all test result file (even without errors / failures)'
    )

    return parser


def main(opts):
    # use PWD in order to work when being invoked in a symlinked location
    cwd = os.getenv('PWD', os.curdir)
    opts.basepath = os.path.abspath(os.path.join(cwd, opts.basepath))

    # verify that workspace folder exists
    if not os.path.exists(opts.basepath):
        raise RuntimeError("The specified base path '%s' does not exist" %
                           opts.basepath)

    try:
        results = collect_test_results(opts.basepath, verbose=opts.verbose)
        _, sum_errors, sum_failures, sum_skipped = aggregate_results(results)
        print_summary(results, show_stable=opts.verbose)
        if sum_errors or sum_failures:
            return 1
    except Exception as e:
        print(', '.join([line.strip() for line
              in traceback.format_exception_only(type(e), e)]),
              file=sys.stderr)
        return 2


def collect_test_results(test_results_dir, verbose=False):
    """
    Collect test results by parsing all xml files in a given path.

    Each file is interpreted as a JUnit result file.

    :param test_results_dir: str foldername
    :returns: dict {rel_path, (num_tests, num_errors, num_failures)}
    """
    results = {}
    for dirpath, dirnames, filenames in os.walk(test_results_dir):
        # do not recurse into folders starting with a dot
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for filename in [f for f in filenames if f.endswith('.xml')]:
            filename_abs = os.path.join(dirpath, filename)
            name = filename_abs[len(test_results_dir) + 1:]
            try:
                num_tests, num_errors, num_failures, num_skipped = read_junit(filename_abs)
            except TypeError as e:
                if verbose:
                    print("Skipping '%s': %s" % (name, str(e)), file=sys.stderr)
                continue
            except Exception as e:
                print("Skipping '%s': %s" %
                      (name, ', '.join([line.strip() for line
                       in traceback.format_exception_only(type(e), e)])),
                      file=sys.stderr)
                continue
            results[name] = (num_tests, num_errors, num_failures, num_skipped)
    return results


def read_junit(filename):
    """
    Parse xml file expected to follow junit/gtest conventions.

    See http://code.google.com/p/googletest/wiki/AdvancedGuide#Generating_an_XML_Report :cmt:`# noqa`

    :param filename: str junit xml file name
    :returns: num_tests, num_errors, num_failures
    :raises IOError: if filename does not exist
    :raises ParseError: if xml is not well-formed
    :raises TypeError: if the root node if not named 'testsuite'
    """
    tree = ElementTree()
    root = tree.parse(filename)
    if root.tag not in ['testsuite', 'testsuites']:
        raise TypeError(
            'seem not to be a JUnit result file '
            "(does not have a 'testsuite' or 'testsuites' root tag)")
    num_tests = int(root.attrib['tests'])
    num_errors = int(root.attrib.get('errors', 0))
    num_failures = int(root.attrib['failures'])
    num_skipped = int(root.attrib.get('skip', 0))
    return (num_tests, num_errors, num_failures, num_skipped)


def aggregate_results(results, callback_per_result=None):
    """
    Aggregate results.

    :param results: dict as from test_results()
    :returns: tuple (num_tests, num_errors, num_failures)
    """
    sum_tests = sum_errors = sum_failures = sum_skipped = 0
    for name in sorted(results.keys()):
        (num_tests, num_errors, num_failures, num_skipped) = results[name]
        sum_tests += num_tests
        sum_errors += num_errors
        sum_failures += num_failures
        sum_skipped += num_skipped
        if callback_per_result:
            callback_per_result(name, num_tests, num_errors, num_failures, num_skipped)
    return sum_tests, sum_errors, sum_failures, sum_skipped


def print_summary(results, show_stable=False, show_unstable=True):
    """
    Print summary to stdout.

    :param results: dict as from test_results()
    :param show_stable: print tests without errors or failures
    :param show_unstable: print tests with errors or failures
    """
    def callback(name, num_tests, num_errors, num_failures, num_skipped):
        if show_stable and not (num_errors or num_failures):
            print('%s: %d tests, %d skipped' % (name, num_tests, num_skipped))
        if show_unstable and (num_errors or num_failures):
            print('%s: %d tests, %d skipped, %d errors, %d failures' %
                  (name, num_tests, num_skipped, num_errors, num_failures))
    sum_tests, sum_errors, sum_failures, sum_skipped = aggregate_results(results, callback)
    print('Summary: %d tests, %d errors, %d failures, %d skipped' %
          (sum_tests, sum_errors, sum_failures, sum_skipped))
