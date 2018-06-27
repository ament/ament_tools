from __future__ import print_function

import sys

from setuptools import find_packages
from setuptools import setup

if sys.version_info < (3, 5):
    print('ament requires Python 3.5 or higher.', file=sys.stderr)
    sys.exit(1)

setup(
    name='ament_tools',
    version='0.5.0',
    packages=find_packages(exclude=['test', 'test.*']),
    install_requires=['ament-package', 'osrf_pycommon'],
    zip_safe=False,
    data_files=[
        ('share/ament_tools/environment',
            [
                'completion/ament-completion.bash',
                'completion/ament-completion.zsh',
            ]),
    ],
    author='Dirk Thomas, William Woodall',
    author_email='dthomas@osrfoundation.org, william@osrfoundation.org',
    maintainer='William Woodall',
    maintainer_email='william@osrfoundation.org',
    url='https://github.com/ament/ament_tools/wiki',
    download_url='https://github.com/ament/ament_tools/releases',
    keywords=['ROS'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Topic :: Software Development',
    ],
    description='Ament is a build system for federated packages.',
    long_description="""\
Ament defines metainformation for packages, their dependencies,
and provides tooling to build these federated packages together.""",
    license='Apache License, Version 2.0',
    test_suite='test',
    entry_points={
        'console_scripts': [
            'ament = ament_tools.commands.ament:main',
        ],
        'ament.verbs': [
            'build = ament_tools.verbs.build:entry_point_data',
            'build_pkg = ament_tools.verbs.build_pkg:entry_point_data',
            'list_dependencies = ament_tools.verbs.list_dependencies:entry_point_data',
            'list_packages = ament_tools.verbs.list_packages:entry_point_data',
            'package_name = ament_tools.verbs.package_name:entry_point_data',
            'package_version = ament_tools.verbs.package_version:entry_point_data',
            'test = ament_tools.verbs.test:entry_point_data',
            'test_pkg = ament_tools.verbs.test_pkg:entry_point_data',
            'test_results = ament_tools.verbs.test_results:entry_point_data',
            'uninstall = ament_tools.verbs.uninstall:entry_point_data',
            'uninstall_pkg = ament_tools.verbs.uninstall_pkg:entry_point_data',
        ],
        'ament.build_types': [
            'ament_cmake = ament_tools.build_types.ament_cmake:AmentCmakeBuildType',
            'ament_python = ament_tools.build_types.ament_python:AmentPythonBuildType',
            'cmake = ament_tools.build_types.cmake:CmakeBuildType',
        ],
        'ament.package_types': [
            'ament = ament_tools.package_types.ament:entry_point_data',
            'cmake = ament_tools.package_types.cmake:entry_point_data',
            'python = ament_tools.package_types.python:entry_point_data',
        ],
    },
)
