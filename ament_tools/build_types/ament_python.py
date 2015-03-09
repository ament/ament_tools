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

PYTHON_EXECUTABLE = sys.executable
NOSETESTS_EXECUTABLE = None
try:
    import nose
    # Use the -m module option for executing nose, to ensure we get the desired version.
    # Looking for just nosetest or nosetest3 on the PATH was not reliable in virtualenvs.
    NOSETESTS_EXECUTABLE = [PYTHON_EXECUTABLE, '-m', nose.__name__]
except ImportError:
    pass

IS_WINDOWS = os.name == 'nt'


class AmentPythonBuildType(BuildType):
    build_type = 'ament_python'
    description = "ament package built with Python"

    def on_build(self, context):
        # expand all templates in build space
        yield BuildAction(self._build_action, type='function')

    def _build_action(self, context):
        # expand environment hook for PYTHONPATH
        ext = '.bat.in' if IS_WINDOWS else '.sh.in'
        template_path = get_environment_hook_template_path('pythonpath' + ext)
        content = configure_file(template_path, {
            'PYTHON_INSTALL_DIR': self._get_python_lib(context),
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
            if IS_WINDOWS and not name.endswith('.bat.in'):
                continue
            if not IS_WINDOWS and name.endswith('.bat.in'):
                continue
            assert name.endswith('.in')
            template_path = get_package_level_template_path(name)
            variables = {'CMAKE_INSTALL_PREFIX': context.install_space}
            if name[:-3].endswith('.sh'):
                variables['ENVIRONMENT_HOOKS'] = \
                    'ament_append_value AMENT_ENVIRONMENT_HOOKS "%s"\n' % \
                    os.path.join(
                        '$AMENT_CURRENT_PREFIX', pythonpath_environment_hook)
            elif name[:-3].endswith('.bat'):
                variables['ENVIRONMENT_HOOKS_BAT'] = \
                    'call:ament_append_value AMENT_ENVIRONMENT_HOOKS %s\n' % \
                    os.path.join(
                        '%AMENT_CURRENT_PREFIX%', pythonpath_environment_hook)
            content = configure_file(template_path, variables)
            destination_path = os.path.join(
                context.build_space,
                'share', context.package_manifest.name,
                name[:-3])
            with open(destination_path, 'w') as h:
                h.write(content)

        # expand prefix-level setup files
        for name in get_prefix_level_template_names():
            if IS_WINDOWS and not name.endswith('.bat.in'):
                continue
            if not IS_WINDOWS and name.endswith('.bat.in'):
                continue
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
        # Execute nosetests
        # and avoid placing any files in the source space
        coverage_file = os.path.join(context.build_space, '.coverage')
        additional_lines = []
        if IS_WINDOWS:
            additional_lines.append('set "COVERAGE_FILE=%s"' % coverage_file)
        else:
            additional_lines.append('export COVERAGE_FILE=%s' % coverage_file)
        prefix = self._get_command_prefix(
            'test', context, additional_lines=additional_lines)
        xunit_file = os.path.join(context.build_space, 'nosetests.xml')
        assert NOSETESTS_EXECUTABLE, 'Could not find nosetests'
        cmd = NOSETESTS_EXECUTABLE + [
            '--nocapture',
            '--with-xunit', '--xunit-file=%s' % xunit_file,
            '--with-coverage', '--cover-erase',
            '--cover-tests', '--cover-branches',
        ]
        # coverage for all root-packages
        packages = setuptools.find_packages(
            context.source_space, exclude=['*.*'])
        for package in packages:
            if package in ['test', 'tests']:
                continue
            cmd += ['--cover-package=%s' % package]
        yield BuildAction(prefix + cmd, cwd=context.source_space)

    def on_install(self, context):
        yield BuildAction(self._install_action_files, type='function')

        # setup.py egg_info requires the --egg-base to exist
        if not os.path.exists(context.build_space):
            os.makedirs(context.build_space)
        # setup.py install/develop requires the PYTHONPATH to exist
        python_path = os.path.join(
            context.install_space, self._get_python_lib(context))
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
                self._add_install_layout(context, cmd)
                yield BuildAction(prefix + cmd, cwd=context.build_space)

            # Execute the setup.py install step with lots of arguments
            # to avoid placing any files in the source space
            cmd = [
                PYTHON_EXECUTABLE, 'setup.py',
                'egg_info', '--egg-base', context.build_space,
                'build', '--build-base', os.path.join(
                    context.build_space, 'build'),
                'install', '--prefix', context.install_space,
                '--record', os.path.join(context.build_space, 'install.log'),
            ]
            self._add_install_layout(context, cmd)
            cmd += [
                'bdist_egg', '--dist-dir', os.path.join(
                    context.build_space, 'dist'),
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
            self._add_install_layout(context, cmd)
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
<<<<<<< HEAD
            with open(marker_file, 'w'):
=======
            with open(marker_file, 'w'):  # "touching" the file
>>>>>>> [windows] support ament cmake and python
                pass

        # deploy environment hook for PYTHONPATH
        deploy_file = 'pythonpath' + ('.bat' if IS_WINDOWS else '.sh')
        self._deploy(
            context, context.build_space,
            os.path.join(
                'share', context.package_manifest.name, 'environment',
                deploy_file))
        # deploy package-level setup files
        for name in get_package_level_template_names():
            assert name.endswith('.in')
            if IS_WINDOWS and not name.endswith('.bat.in'):
                continue
            if not IS_WINDOWS and name.endswith('.bat.in'):
                continue
            self._deploy(
                context, context.build_space,
                os.path.join(
                    'share', context.package_manifest.name, name[:-3]))

        # deploy prefix-level setup files
        for name in get_prefix_level_template_names():
            if IS_WINDOWS and not name[:-3].endswith('.bat'):
                continue
            if not IS_WINDOWS and name[:-3].endswith('.bat'):
                continue
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

    def _add_install_layout(self, context, cmd):
        if 'dist-packages' in self._get_python_lib(context):
            cmd += ['--install-layout', 'deb']

    def _get_python_lib(self, context):
        path = get_python_lib(prefix=context.install_space)
        return os.path.relpath(path, start=context.install_space)

    def _get_command_prefix(self, name, context, additional_lines=None):
        if IS_WINDOWS:
            return self._get_command_prefix_windows(name, context,
                                                    additional_lines)
        else:
            return self._get_command_prefix_unix(name, context,
                                                 additional_lines)

    def _get_command_prefix_windows(self, name, context, additional_lines):
        lines = []
        lines.append('@echo off')
        for path in context.build_dependencies:
            local_setup = os.path.join(path, 'local_setup.bat')
            lines.append('if exist "{0}" call "{0}"'.format(local_setup))
        lines.append(
            'set "PYTHONPATH={0};%PYTHONPATH%"'
            .format(os.path.join(context.install_space,
                                 self._get_python_lib(context))))
        if additional_lines:
            lines += additional_lines
        lines += ['%*']
        lines += ['if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%']

        generated_file = os.path.join(
            context.build_space, '%s__%s.bat' %
            (AmentPythonBuildType.build_type, name))
        with open(generated_file, 'w') as h:
            for line in lines:
                h.write('%s\n' % line)

        return [generated_file]

    def _get_command_prefix_unix(self, name, context, additional_lines):
        lines = []
        lines.append('#!/usr/bin/env sh\n')
        for path in context.build_dependencies:
            local_setup = os.path.join(path, 'local_setup.sh')
            lines.append('if [ -f "%s" ]; then' % local_setup)
            lines.append('  . "%s"' % local_setup)
            lines.append('fi')
        lines.append(
            'export PYTHONPATH=%s:$PYTHONPATH' %
            os.path.join(context.install_space, self._get_python_lib(context)))
        if additional_lines:
            lines += additional_lines

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
                context.install_space, self._get_python_lib(context),
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
