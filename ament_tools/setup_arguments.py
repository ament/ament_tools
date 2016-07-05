# Copyright 2015 Open Source Robotics Foundation, Inc.
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

import os
import distutils.core
try:
    import setuptools
except ImportError:
    pass
from threading import Lock

setup_lock = None


def get_setup_arguments(setup_py_path):
    """
    Capture the arguments of the setup() function in the setup.py file.

    :param setup_py_path: the path to the setup.py file
    :returns: a dictionary containing the arguments of the setup() function
    """
    global setup_lock
    if not setup_lock:
        setup_lock = Lock()
    assert os.path.basename(setup_py_path) == 'setup.py'
    # prevent side effects in other threads
    with setup_lock:
        # change to the directory containing the setup.py file
        old_cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.abspath(setup_py_path)))
        try:
            data = {}
            mock_setup = create_mock_setup_function(data)
            # replace setup() function of distutils and setuptools
            # in order to capture its arguments
            try:
                distutils_setup = distutils.core.setup
                distutils.core.setup = mock_setup
                try:
                    setuptools_setup = setuptools.setup
                    setuptools.setup = mock_setup
                except NameError:
                    pass
                # evaluate the setup.py file
                with open('setup.py', 'r') as h:
                    exec(h.read())
            finally:
                distutils.core.setup = distutils_setup
                try:
                    setuptools.setup = setuptools_setup
                except NameError:
                    pass
            return data

        finally:
            os.chdir(old_cwd)


def create_mock_setup_function(data):
    """
    Create a mock function to capture its arguments.

    It can replace either distutils.core.setup or setuptools.setup.

    :param data: a dictionary which is updated with the captured arguments
    :returns: a function to replace disutils.core.setup and setuptools.setup
    """
    def setup(*args, **kwargs):
        if args:
            raise RuntimeError(
                'setup() function invoked with positional arguments')

        if 'name' not in kwargs:
            raise RuntimeError(
                "setup() function invoked without the keyword argument 'name'")

        data.update(kwargs)

    return setup


def get_data_files_mapping(data_files):
    """
    Transform the data_files structure into a dictionary.

    :param data_files: either a list of source files or
      a list of tuples where the first element is the destination path and
      the second element is a list of source files
    :returns: a dictionary mapping the source file to a destination file
    """
    mapping = {}
    for data_file in data_files:
        if isinstance(data_file, tuple):
            assert len(data_file) == 2
            dest = data_file[0]
            assert not os.path.isabs(dest)
            sources = data_file[1]
            assert isinstance(sources, list)
            for source in sources:
                assert not os.path.isabs(source)
                mapping[source] = os.path.join(dest, os.path.basename(source))
        else:
            assert not os.path.isabs(data_file)
            mapping[data_file] = os.path.basename(data_file)
    return mapping
