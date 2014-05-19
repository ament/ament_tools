#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name='ament_tools',
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    install_requires=['ament-package'],
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
    long_description='''\
Ament defines metainformation for packages, their dependencies,
and provides tooling to build these federated packages together.''',
    license='Apache License, Version 2.0',
    test_suite='test',
    entry_points={
        'console_scripts': [
            'ament = ament_tools.commands.ament:main',
        ],
        'ament.commands': [
            'list_packages = ament_tools.commands.list_packages:entry_point_data',
            'package_name = ament_tools.commands.package_name:entry_point_data',
            'package_version = ament_tools.commands.package_version:entry_point_data',
        ]
    }
)
