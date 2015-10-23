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

import json
import os

from ament_package.templates import configure_file
from ament_package.templates import get_package_level_template_names
from ament_package.templates import get_package_level_template_path


def expand_package_level_setup_files(context, environment_hooks, environment_hooks_path):
    destinations = []

    for name in get_package_level_template_names():
        assert name.endswith('.in')

        local_environment_hooks = []
        if os.path.splitext(name[:-3])[1] in ['.sh', '.bat']:
            local_environment_hooks.extend(environment_hooks)

        # check if any data files are environment hooks (Python only)
        for data_file in context.get('setup.py', {}).get('data_files', {}).values():
            if not data_file.startswith(environment_hooks_path):
                continue
            # ignore data files with different extensions
            if os.path.splitext(data_file)[1] != os.path.splitext(name[:-3])[1]:
                continue
            local_environment_hooks.append(data_file)

        template_path = get_package_level_template_path(name)
        variables = {'CMAKE_INSTALL_PREFIX': context.install_space}
        if name[:-3].endswith('.bat'):
            variables['PROJECT_NAME'] = context.package_manifest.name
        if local_environment_hooks:
            if name[:-3].endswith('.bat'):
                t = 'call:ament_append_value AMENT_ENVIRONMENT_HOOKS[%s] "%s"\n'
                variables['ENVIRONMENT_HOOKS'] = t % (
                    context.package_manifest.name,
                    ';'.join([
                        os.path.join('%AMENT_CURRENT_PREFIX%', environment_hook)
                        for environment_hook in local_environment_hooks
                    ])
                )
            else:
                variables['ENVIRONMENT_HOOKS'] = \
                    'ament_append_value AMENT_ENVIRONMENT_HOOKS "%s"\n' % \
                    ':'.join([
                        os.path.join('$AMENT_CURRENT_PREFIX', environment_hook)
                        for environment_hook in local_environment_hooks
                    ])
        content = configure_file(template_path, variables)
        destination_path = os.path.join(
            context.build_space,
            'share', context.package_manifest.name,
            name[:-3])
        destination_dir = os.path.dirname(destination_path)
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
        destinations.append(destination_path)
        with open(destination_path, 'w') as h:
            h.write(content)

    return destinations


def get_cached_config(build_space, name):
    path = os.path.join(build_space, '{name}.cache'.format(name=name))
    if not os.path.isfile(path):
        return None
    with open(path, 'r') as f:
        return json.loads(f.read())


def set_cached_config(build_space, name, value):
    if not os.path.isdir(build_space):
        assert not os.path.isfile(build_space), \
            ("build_space cannot be a file: {build_space}"
             .format(build_space=build_space))
        os.makedirs(build_space)
    path = os.path.join(build_space, '{name}.cache'.format(name=name))
    with open(path, 'w') as f:
        f.write(json.dumps(value, sort_keys=True))
