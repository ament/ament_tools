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

"""Implements the BuildType support for cmake based ament packages."""

from distutils.sysconfig import get_python_lib
from distutils.version import LooseVersion
import os
import re
import setuptools
import shutil
import sys

from ament_package.templates import configure_file
from ament_package.templates import get_environment_hook_template_path
from ament_package.templates import get_package_level_template_names
from ament_tools.build_type import BuildAction
from ament_tools.build_type import BuildType
from ament_tools.build_types.common import expand_package_level_setup_files
from ament_tools.helper import deploy_file
from ament_tools.setup_arguments import get_data_files_mapping
from ament_tools.setup_arguments import get_setup_arguments

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
        self._update_context_with_setup_arguments(context)

        # expand all templates in build space
        yield BuildAction(self._build_action, type='function')

    def _build_action(self, context):
        environment_hooks_path = os.path.join(
            'share', context.package_manifest.name, 'environment')

        ext = '.sh' if not IS_WINDOWS else '.bat'
        path_environment_hook = os.path.join(
            environment_hooks_path, 'path' + ext)
        # expand environment hook for PYTHONPATH
        ext = '.sh.in' if not IS_WINDOWS else '.bat.in'
        template_path = get_environment_hook_template_path('pythonpath' + ext)
        content = configure_file(template_path, {
            'PYTHON_INSTALL_DIR': self._get_python_lib(context),
        })
        pythonpath_environment_hook = os.path.join(
            environment_hooks_path, os.path.basename(template_path)[:-3])
        destination_path = os.path.join(
            context.build_space, pythonpath_environment_hook)
        destination_dir = os.path.dirname(destination_path)
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
        with open(destination_path, 'w') as h:
            h.write(content)

        environment_hooks = [
            path_environment_hook,
            pythonpath_environment_hook,
        ]

        # expand package-level setup files
        expand_package_level_setup_files(context, environment_hooks, environment_hooks_path)

    def on_test(self, context):
        # Execute nosetests
        # and avoid placing any files in the source space
        coverage_file = os.path.join(context.build_space, '.coverage')
        additional_lines = []
        if not IS_WINDOWS:
            additional_lines.append('export COVERAGE_FILE="%s"' % coverage_file)
        else:
            additional_lines.append('set "COVERAGE_FILE=%s"' % coverage_file)
        prefix = self._get_command_prefix(
            'test', context, additional_lines=additional_lines)
        xunit_file = os.path.join(
            context.build_space, 'test_results',
            context.package_manifest.name, 'nosetests.xunit.xml')
        if not os.path.exists(os.path.dirname(xunit_file)):
            os.makedirs(os.path.dirname(xunit_file))
        assert NOSETESTS_EXECUTABLE, 'Could not find nosetests'
        coverage_xml_file = os.path.join(context.build_space, 'coverage.xml')
        cmd = NOSETESTS_EXECUTABLE + [
            '--nocapture',
            '--with-xunit', '--xunit-file=%s' % xunit_file,
            '--with-coverage', '--cover-erase',
            '--cover-tests', '--cover-branches',
            '--cover-inclusive',
            '--cover-xml', '--cover-xml-file=%s' % coverage_xml_file,
        ]
        if LooseVersion(nose.__version__) >= LooseVersion('1.3.5'):
            cmd += [
                '--xunit-testsuite-name=%s.nosetests' %
                context.package_manifest.name]
        # coverage for all root-packages
        packages = setuptools.find_packages(
            context.source_space, exclude=['*.*'])
        for package in packages:
            if package in ['test', 'tests']:
                continue
            cmd += ['--cover-package=%s' % package]
        yield BuildAction(prefix + cmd, cwd=context.source_space)

    def on_install(self, context):
        self._update_context_with_setup_arguments(context)

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
            for action in self._undo_develop(context, prefix) or []:
                yield action

            # Execute the setup.py install step with lots of arguments
            # to avoid placing any files in the source space
            cmd = [
                PYTHON_EXECUTABLE, 'setup.py',
                'egg_info', '--egg-base', context.build_space,
                'build', '--build-base', os.path.join(
                    context.build_space, 'build'),
                'install', '--prefix', context.install_space,
                '--install-scripts', os.path.join(context.install_space, 'bin'),
                '--record', os.path.join(context.build_space, 'install.log'),
                # prevent installation of dependencies specified in the setup.py file
                '--single-version-externally-managed',
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
                '--script-dir', os.path.join(context.install_space, 'bin'),
                '--no-deps',
            ]
            if context['setup.py']['data_files']:
                cmd += ['install_data', '--install-dir', context.install_space]
            self._add_install_layout(context, cmd)
            yield BuildAction(prefix + cmd, cwd=context.build_space)

    def _undo_develop(self, context, prefix):
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

    def _install_action_files(self, context):
        # deploy package manifest
        deploy_file(
            context, context.source_space, 'package.xml',
            dst_subfolder=os.path.join('share', context.package_manifest.name))

        # create marker file
        marker_file = os.path.join(
            context.install_space,
            'share', 'ament_index', 'resource_index', 'packages',
            context.package_manifest.name)
        if not os.path.exists(marker_file):
            marker_dir = os.path.dirname(marker_file)
            if not os.path.exists(marker_dir):
                os.makedirs(marker_dir)
            with open(marker_file, 'w'):  # "touching" the file
                pass

        # deploy PATH environment hook
        ext = '.sh' if not IS_WINDOWS else '.bat'
        template_path = get_environment_hook_template_path('path' + ext)
        deploy_file(
            context, os.path.dirname(template_path), os.path.basename(template_path),
            dst_subfolder=os.path.join('share', context.package_manifest.name, 'environment'))

        # deploy PYTHONPATH environment hook
        destination_file = 'pythonpath' + ('.sh' if not IS_WINDOWS else '.bat')
        deploy_file(
            context, context.build_space,
            os.path.join(
                'share', context.package_manifest.name, 'environment',
                destination_file))

        # deploy package-level setup files
        for name in get_package_level_template_names():
            assert name.endswith('.in')
            deploy_file(
                context, context.build_space,
                os.path.join(
                    'share', context.package_manifest.name, name[:-3]))

    def _add_install_layout(self, context, cmd):
        if 'dist-packages' in self._get_python_lib(context):
            cmd += ['--install-layout', 'deb']

    def _get_python_lib(self, context):
        path = get_python_lib(prefix=context.install_space)
        return os.path.relpath(path, start=context.install_space)

    def _get_command_prefix(self, name, context, additional_lines=None):
        if not IS_WINDOWS:
            return self._get_command_prefix_unix(name, context,
                                                 additional_lines)
        else:
            return self._get_command_prefix_windows(name, context,
                                                    additional_lines)

    def _get_command_prefix_windows(self, name, context, additional_lines):
        lines = []
        lines.append('@echo off')
        for path in context.build_dependencies:
            local_setup = os.path.join(path, 'local_setup.bat')
            lines.append(
                'if "%AMENT_TRACE_SETUP_FILES%" NEQ "" echo call "{0}"'.format(local_setup))
            lines.append('if exist "{0}" call "{0}"'.format(local_setup))
            lines.append('')
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
            lines.append('if [ -n "$AMENT_TRACE_SETUP_FILES" ]; then')
            lines.append('  echo ". \\"%s\\""' % local_setup)
            lines.append('fi')
            lines.append('if [ -f "%s" ]; then' % local_setup)
            lines.append('  . "%s"' % local_setup)
            lines.append('fi')
            lines.append('')
        lines.append(
            'export PYTHONPATH="%s:$PYTHONPATH"' %
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
        self._undo_install(context)

        items = ['setup.py']
        # add all first level packages
        items += [p for p in context['setup.py']['packages'] if '.' not in p]
        items += list(context['setup.py']['data_files'].keys())

        # symlink files / folders from source space into build space
        for item in items:
            src = os.path.join(context.source_space, item)
            dst = os.path.join(context.build_space, item)
            dst_dir = os.path.dirname(dst)
            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)
            if os.path.exists(dst):
                if not os.path.islink(dst) or \
                        not os.path.samefile(src, dst):
                    if os.path.isfile(dst):
                        os.remove(dst)
                    elif os.path.isdir(dst):
                        shutil.rmtree(dst)
            if not os.path.exists(dst):
                os.symlink(src, dst)

    def _undo_install(self, context):
        # Undo previous install if install.log is found
        install_log = os.path.join(context.build_space, 'install.log')
        if os.path.exists(install_log):
            with open(install_log, 'r') as h:
                lines = [l.rstrip() for l in h.readlines()]
            directories = []
            for line in lines:
                if os.path.exists(line) and \
                        line.startswith(context.install_space):
                    if not os.path.isdir(line):
                        os.remove(line)
                    else:
                        directories.append(line)
            for d in sorted(directories, reverse=True):
                # only remove empty directories
                try:
                    os.rmdir(d)
                except OSError:
                    pass
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

    def on_uninstall(self, context):
        yield BuildAction(self._uninstall_action_files, type='function')

        # Figure out if there is a setup file to source
        prefix = self._get_command_prefix('uninstall', context)

        for action in self._undo_develop(context, prefix) or []:
            yield action
        self._undo_install(context)

    def _uninstall_action_files(self, context):
        files = [
            # package manifest
            os.path.join('share', context.package_manifest.name, 'package.xml'),
            # marker file
            os.path.join(
                'share', 'ament_index', 'resource_index', 'packages',
                context.package_manifest.name),
        ]
        # environment hooks
        for env_hook_name in ['path', 'pythonpath']:
            deploy_file = env_hook_name + ('.sh' if not IS_WINDOWS else '.bat')
            files.append(
                os.path.join('share', context.package_manifest.name, 'environment', deploy_file))
        # package-level setup files
        for name in get_package_level_template_names():
            assert name.endswith('.in')
            files.append(os.path.join('share', context.package_manifest.name, name[:-3]))

        # remove all files
        for rel_path in files:
            abs_path = os.path.join(context.install_space, rel_path)
            if os.path.exists(abs_path):
                os.remove(abs_path)
                self._remove_empty_directories(context, os.path.dirname(abs_path))

    def _remove_empty_directories(self, context, path):
        assert path.startswith(context.install_space), \
            "The path '%s' must be within the install space '%s'" % (path, context.install_space)
        if path == context.install_space:
            return
        try:
            os.rmdir(path)
            self._remove_empty_directories(context, os.path.dirname(path))
        except OSError:
            # directory is likely not empty
            pass

    def _update_context_with_setup_arguments(self, context):
        if 'setup.py' in context:
            return
        # check setup.py file for data files and packages
        args = get_setup_arguments(os.path.join(context.source_space, 'setup.py'))
        data_files = get_data_files_mapping(args.get('data_files', []))
        context['setup.py'] = {
            'data_files': data_files,
            'packages': args['packages'],
        }
