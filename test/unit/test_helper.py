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

from ament_tools import helper


def test_extract_jobs_flags():
    extract_jobs_flags = helper.extract_jobs_flags
    valid_mflags = [
        '-j8 -l8', 'j8 ', '-j', 'j', '-l8', 'l8',
        '-l', 'l', '-j18', ' -j8 l9', '-j1 -l1',
        '--jobs=8', '--jobs 8', '--jobs', '--load-average',
        '--load-average=8', '--load-average 8', '--jobs=8 -l9',
    ]
    results = [
        '-j8 -l8', 'j8', '-j', 'j', '-l8', 'l8',
        '-l', 'l', '-j18', '-j8 l9', '-j1 -l1',
        '--jobs=8', '--jobs 8', '--jobs', '--load-average',
        '--load-average=8', '--load-average 8', '--jobs=8 -l9',
    ]
    for mflag, result in zip(valid_mflags, results):
        match = extract_jobs_flags(mflag)
        assert match == result, "should match '{0}'".format(mflag)
        print('--')
        print("input:    '{0}'".format(mflag))
        print("matched:  '{0}'".format(match))
        print("expected: '{0}'".format(result))
    invalid_mflags = ['', '--jobs= 8', '--jobs8']
    for mflag in invalid_mflags:
        match = extract_jobs_flags(mflag)
        assert match is None, "should not match '{0}'".format(mflag)


def test_extract_argument_group():
    extract_argument_group = helper.extract_argument_group
    # Example 1 from docstring
    args = ['foo', '--args', 'bar', '--baz']
    expected = (['foo'], ['bar', '--baz'])
    results = extract_argument_group(args, '--args')
    assert expected == results, (args, expected, results)
    # Example 2 from docstring
    args = ['foo', '--args', 'bar', '--baz', '---', '--', '--foo-option']
    expected = (['foo', '--foo-option'], ['bar', '--baz', '--'])
    results = extract_argument_group(args, '--args')
    assert expected == results, (args, expected, results)
    # Example 3 from docstring
    args = ['foo',
            '--args', 'ping', '--',
            'bar',
            '--args', 'pong', '--',
            'baz',
            '--args', '--']
    expected = (['foo', 'bar', 'baz'], ['ping', 'pong'])
    results = extract_argument_group(args, '--args')
    assert expected == results, (args, expected, results)
    # Example with delimiter but no arguments
    args = ['foo', '--args']
    expected = (['foo'], [])
    results = extract_argument_group(args, '--args')
    assert expected == results, (args, expected, results)
    # Example with no delimiter
    args = ['foo', 'bar']
    expected = (['foo', 'bar'], [])
    results = extract_argument_group(args, '--args')
    assert expected == results, (args, expected, results)
