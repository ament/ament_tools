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

"""Implements the BuildType support for cmake based ament packages."""

from distutils.sysconfig import get_python_lib
import filecmp
import os
import shutil
import stat
import sys

from ament_package.templates import configure_file
from ament_package.templates import get_environment_hook_template_path
from ament_package.templates import get_package_level_template_names
from ament_package.templates import get_package_level_template_path
from ament_package.templates import get_prefix_level_template_names
from ament_package.templates import get_prefix_level_template_path
from ament_tools.build_type import BuildAction
from ament_tools.build_type import BuildType

from ament_tools.context import ContextExtender

PYTHON_EXECUTABLE = sys.executable


class AmentPythonBuildType(BuildType):
    build_type = 'ament_python'
    description = "ament package built with Python"

    def get_command_prefix(self, context):
        prefix = []
        local_setup = os.path.join(context.install_space, 'local_setup.sh')
        if os.path.isfile(local_setup):
            prefix = ['.', local_setup, '&&']
        return prefix

    def on_build(self, context):
        # expand all templates in build space
        yield BuildAction(self._build_action, type='function')

        # Figure out if there is a setup file to source
        prefix = self.get_command_prefix(context)

        # Execute the setup.py build step
        yield BuildAction(prefix + [
            PYTHON_EXECUTABLE, 'setup.py',
            'build', '--build-base', context.build_space,
        ], cwd=context.source_space)

    def _build_action(self, context):
        # setup.py install requires the --build-base to exist
        if not os.path.exists(context.build_space):
            os.makedirs(context.build_space)

        # expand environment hook for PYTHONPATH
        template_path = get_environment_hook_template_path('pythonpath.sh.in')
        content = configure_file(template_path, {
            'PYTHON_INSTALL_DIR': get_python_lib(prefix=''),
        })
        pythonpath_environment_hook = os.path.join(
            'share', context.package_manifest.name, 'environment',
            os.path.basename(template_path)[:-3])
        destination_path = os.path.join(
            context.build_space, pythonpath_environment_hook)
        destination_dir = os.path.dirname(destination_path)
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
        with open(destination_path, 'w') as h:
            h.write(content)

        # expand package-level setup files
        for name in get_package_level_template_names():
            assert name.endswith('.in')
            template_path = get_package_level_template_path(name)
            variables = {
                'CMAKE_INSTALL_PREFIX': context.install_space,
                'SOURCE_HOOKS': ''}
            if name[:-3].endswith('.sh'):
                variables['SOURCE_HOOKS'] = '. %s' % (
                    os.path.join(
                        '$AMENT_CURRENT_PREFIX', pythonpath_environment_hook))
            content = configure_file(template_path, variables)
            destination_path = os.path.join(
                context.build_space,
                'share', context.package_manifest.name,
                name[:-3])
            with open(destination_path, 'w') as h:
                h.write(content)

        # expand prefix-level setup files
        for name in get_prefix_level_template_names():
            if name.endswith('.in'):
                template_path = get_prefix_level_template_path(name)
                content = configure_file(template_path, {
                    'CMAKE_INSTALL_PREFIX': context.install_space,
                })
                destination_path = os.path.join(
                    context.build_space, name[:-3])
                with open(destination_path, 'w') as h:
                    h.write(content)

    def on_test(self, context):
        raise NotImplementedError()

    def on_install(self, context):
        yield BuildAction(self._install_action, type='function')

        # Figure out if there is a setup file to source
        prefix = self.get_command_prefix(context)

        # Execute the setup.py install step
        cmd = [
            PYTHON_EXECUTABLE, 'setup.py',
            'build', '--build-base', context.build_space,
            'install', '--prefix', context.install_space,
        ]
        if 'dist-packages' in get_python_lib(prefix=''):
            cmd += ['--install-layout', 'deb']
        yield BuildAction(prefix + cmd, cwd=context.source_space)

    def _install_action(self, context):
        # deploy package manifest
        self._deploy(context, context.source_space, 'package.xml',
                     executable=False)

        # create marker file
        marker_file = os.path.join(
            context.install_space,
            'share', 'ament_index', 'resource_index', 'packages',
            context.package_manifest.name)
        if not os.path.exists(marker_file):
            marker_dir = os.path.dirname(marker_file)
            if not os.path.exists(marker_dir):
                os.makedirs(marker_dir)
            with open(marker_file, 'w') as f:
                pass

        # deploy environment hook for PYTHONPATH
        self._deploy(
            context, context.build_space,
            os.path.join(
                'share', context.package_manifest.name, 'environment',
                'pythonpath.sh'))
        # deploy package-level setup files
        for name in get_package_level_template_names():
            assert name.endswith('.in')
            self._deploy(
                context, context.build_space,
                os.path.join(
                    'share', context.package_manifest.name, name[:-3]))

        # deploy prefix-level setup files
        for name in get_prefix_level_template_names():
            if name.endswith('.in'):
                self._deploy(context, context.build_space, name[:-3])
            else:
                template_path = get_prefix_level_template_path(name)
                self._deploy(context, os.path.dirname(template_path),
                             os.path.basename(template_path))

    def _deploy(self, context, source_base_path, filename, executable=True):
        # create destination folder if necessary
        destination_path = os.path.join(context.install_space, filename)
        destination_folder = os.path.dirname(destination_path)
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

        # copy the file if not already there and identical
        source_path = os.path.join(source_base_path, filename)
        if os.path.exists(destination_path) and \
                not filecmp.cmp(source_path, destination_path):
            os.remove(destination_path)
        if not os.path.exists(destination_path):
            shutil.copyfile(source_path, destination_path)

        # set executable bit if necessary
        if executable:
            mode = os.stat(destination_path).st_mode
            new_mode = mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            if new_mode != mode:
                os.chmod(destination_path, new_mode)
