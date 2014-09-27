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
import re
import setuptools
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

    def on_build(self, context):
        # expand all templates in build space
        yield BuildAction(self._build_action, type='function')

    def _build_action(self, context):
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
            variables = {'CMAKE_INSTALL_PREFIX': context.install_space}
            if name[:-3].endswith('.sh'):
                variables['ENVIRONMENT_HOOKS'] = \
                    'ament_append_value AMENT_ENVIRONMENT_HOOKS "%s"\n' % \
                    os.path.join(
                        '$AMENT_CURRENT_PREFIX', pythonpath_environment_hook)
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
        # Execute the setup.py test step
        # and avoid placing any files in the source space
        prefix = self._get_command_prefix('test', context)
        cmd = [
            PYTHON_EXECUTABLE, 'setup.py', 'test',
            'egg_info', '--egg-base', context.build_space,
        ]
        yield BuildAction(prefix + cmd, cwd=context.source_space)

    def on_install(self, context):
        yield BuildAction(self._install_action_files, type='function')

        # setup.py egg_info requires the --egg-base to exist
        if not os.path.exists(context.build_space):
            os.makedirs(context.build_space)
        # setup.py install/develop requires the PYTHONPATH to exist
        python_path = os.path.join(
            context.install_space, get_python_lib(prefix=''))
        if not os.path.exists(python_path):
            os.makedirs(python_path)

        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('install', context)

        if not context.symlink_install:
            # Undo previous develop if .egg-info is found and develop symlinks
            egg_info = os.path.join(context.build_space, '%s.egg-info' %
                                    context.package_manifest.name)
            setup_py_build_space = os.path.join(
                context.build_space, 'setup.py')
            if os.path.exists(egg_info) and \
                    os.path.exists(setup_py_build_space) and \
                    os.path.islink(setup_py_build_space):
                cmd = [
                    PYTHON_EXECUTABLE, 'setup.py',
                    'develop', '--prefix', context.install_space,
                    '--uninstall',
                ]
                if 'dist-packages' in get_python_lib(prefix=''):
                    cmd += ['--install-layout', 'deb']
                yield BuildAction(prefix + cmd, cwd=context.build_space)

            # Execute the setup.py install step with lots of arguments
            # to avoid placing any files in the source space
            cmd = [
                PYTHON_EXECUTABLE, 'setup.py',
                'install', '--prefix', context.install_space,
                '--record', os.path.join(context.build_space, 'install.log'),
            ]
            if 'dist-packages' in get_python_lib(prefix=''):
                cmd += ['--install-layout', 'deb']
            cmd += [
                'build', '--build-base', context.build_space,
                'egg_info', '--egg-base', context.build_space,
                'bdist_egg', '--dist-dir', context.build_space,
            ]
            yield BuildAction(prefix + cmd, cwd=context.source_space)

        else:
            yield BuildAction(self._install_action_python, type='function')

            # Execute the setup.py develop step in build space
            # to avoid placing any files in the source space
            cmd = [
                PYTHON_EXECUTABLE, 'setup.py',
                'develop', '--prefix', context.install_space,
            ]
            if 'dist-packages' in get_python_lib(prefix=''):
                cmd += ['--install-layout', 'deb']
            yield BuildAction(prefix + cmd, cwd=context.build_space)

    def _install_action_files(self, context):
        # deploy package manifest
        self._deploy(
            context, context.source_space, 'package.xml',
            dst_subfolder=os.path.join('share', context.package_manifest.name),
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

    def _deploy(self, context, source_base_path, filename, dst_subfolder='',
                executable=True):
        # create destination folder if necessary
        destination_path = os.path.join(
            context.install_space, dst_subfolder, filename)
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

    def _get_command_prefix(self, name, context):
        lines = []
        lines.append('#!/usr/bin/env sh\n')
        for path in context.build_dependencies:
            local_setup = os.path.join(path, 'local_setup.sh')
            lines.append('if [ -f "%s" ]; then' % local_setup)
            lines.append('  . "%s"' % local_setup)
            lines.append('fi')
        lines.append(
            'export PYTHONPATH=%s:$PYTHONPATH' % os.path.join(
            context.install_space, get_python_lib(prefix='')))

        generated_file = os.path.join(
            context.build_space, '%s__%s.sh' %
            (AmentPythonBuildType.build_type, name))
        with open(generated_file, 'w') as h:
            for line in lines:
                h.write('%s\n' % line)

        return ['.', generated_file, '&&']

    def _install_action_python(self, context):
        # Undo previous install if install.log is found
        install_log = os.path.join(context.build_space, 'install.log')
        if os.path.exists(install_log):
            with open(install_log, 'r') as h:
                lines = [l.rstrip() for l in h.readlines()]
            for line in lines:
                if os.path.exists(line) and \
                        line.startswith(context.install_space):
                    os.remove(line)
            os.remove(install_log)

            # remove entry from easy-install.pth file
            easy_install = os.path.join(
                context.install_space, get_python_lib(prefix=''),
                'easy-install.pth')
            if os.path.exists(easy_install):
                with open(easy_install, 'r') as h:
                    content = h.read()
                pattern = r'^\./%s-\d.+\.egg\n' % \
                    re.escape(context.package_manifest.name)
                matches = re.findall(pattern, content, re.MULTILINE)
                if len(matches) > 0:
                    assert len(matches) == 1, \
                        "Multiple matching entries in '%s'" % easy_install
                    content = content.replace(matches[0], '')
                    with open(easy_install, 'w') as h:
                        h.write(content)

        # Symlink setup.py and all root-packages into build space
        packages = setuptools.find_packages(
            context.source_space, exclude=['*.*'])
        packages.append('setup.py')
        for package in packages:
            src = os.path.join(context.source_space, package)
            dst = os.path.join(context.build_space, package)
            if os.path.exists(dst):
                if not os.path.islink(dst) or \
                        not os.path.samefile(src, dst):
                    os.remove(dst)
            if not os.path.exists(dst):
                os.symlink(src, dst)
