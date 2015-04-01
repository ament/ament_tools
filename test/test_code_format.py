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

import flake8.engine
import os


def test_flake8():
    """Test source code for pyFlakes and PEP8 conformance"""
    flake8style = flake8.engine.StyleGuide(max_line_length=100)
    report = flake8style.options.report
    report.start()
    this_dir = os.path.dirname(os.path.abspath(__file__))
    flake8style.input_dir(os.path.join(this_dir, '..', 'ament_tools'))
    report.stop()
    assert report.total_errors == 0, \
        ("Found '{0}' code style errors (and warnings)."
         .format(report.total_errors))
