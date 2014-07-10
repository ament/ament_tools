from setuptools import find_packages
from setuptools import setup

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
            'list_packages = ament_tools.verbs.list_packages:entry_point_data',
            'package_name = ament_tools.verbs.package_name:entry_point_data',
            'package_version = ament_tools.verbs.package_version:entry_point_data',
            'test = ament_tools.verbs.test:entry_point_data',
            'test_pkg = ament_tools.verbs.test_pkg:entry_point_data',
        ],
        'ament.verb.build_pkg.build_types': [
            'ament_cmake = ament_tools.verbs.build_pkg.build_types.ament_cmake:main',
        ],
        'ament.verb.test_pkg.build_types': [
            'ament_cmake = ament_tools.verbs.test_pkg.build_types.ament_cmake:main',
        ],
    }
)
