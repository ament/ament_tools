"""
Library to find packages in the filesystem.
"""

import os
from ament_package import parse_package, PACKAGE_MANIFEST_FILENAME


def find_package_paths(basepath, exclude_paths=None):
    """
    Crawl the filesystem to find package manifest files.

    When a subfolder contains a file ``AMENT_IGNORE`` it is ignored.

    :param basepath: The path to search in, ``str``
    :param exclude_paths: A list of paths which should not be searched, ``list``
    :returns: A list of relative paths containing package manifest files
    ``list``
    """
    paths = []
    real_exclude_paths = [os.path.realpath(p) for p in exclude_paths] if exclude_paths is not None else []
    for dirpath, dirnames, filenames in os.walk(basepath, followlinks=True):
        if 'AMENT_IGNORE' in filenames or \
            os.path.realpath(dirpath) in real_exclude_paths:
            del dirnames[:]
            continue
        elif PACKAGE_MANIFEST_FILENAME in filenames:
            paths.append(os.path.relpath(dirpath, basepath))
            del dirnames[:]
            continue
        for dirname in dirnames:
            if dirname.startswith('.'):
                dirnames.remove(dirname)
    return paths


def find_packages(basepath, exclude_paths=None):
    """
    Crawl the filesystem to find package manifest files and parses them.

    :param basepath: The path to search in, ``str``
    :param exclude_paths: A list of paths which should not be searched, ``list``
    :returns: A dict mapping relative paths to ``Package`` objects
    ``dict``
    """
    packages = {}
    package_paths = find_package_paths(basepath, exclude_paths=exclude_paths)
    for path in package_paths:
        packages[path] = parse_package(os.path.join(basepath, path))
    return packages


def find_unique_packages(basepath, exclude_paths=None):
    """
    Crawl the filesystem to find package manifest files and parses them.

    :param basepath: The path to search in, ``str``
    :param exclude_paths: A list of paths which should not be searched, ``list``
    :returns: A dict mapping relative paths to ``Package`` objects
    ``dict``
    :raises: :exc:RuntimeError` If multiple packages have the same
    name
    """
    packages = find_packages(basepath, exclude_paths=exclude_paths)
    package_paths_by_name = {}
    for path, package in packages.items():
        if package.name not in package_paths_by_name:
            package_paths_by_name[package.name] = set([])
        package_paths_by_name[package.name].add(path)
    duplicates = dict([(name, paths) for name, paths in package_paths_by_name.items() if len(paths) > 1])
    if duplicates:
        duplicates = ['Multiple packages found with the same name "%s":%s' % (name, ''.join(['\n- %s' % path_ for path_ in sorted(duplicates[name])])) for name in sorted(duplicates.keys())]
        raise RuntimeError('\n'.join(duplicates))
    return packages
