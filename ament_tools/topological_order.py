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

from __future__ import print_function

import copy

from .packages import find_unique_packages


class _PackageDecorator(object):

    def __init__(self, package, path):
        self.package = package
        self.path = path
        # full includes direct build depends and recursive
        # run_depends of these build_depends
        self.depends_for_topological_order = None

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return getattr(self.package, name)

    def calculate_depends_for_topological_order(self, packages):
        """
        Sets self.depends_for_topological_order to the recursive
        dependencies required for topological order. It contains all
        direct build- and buildtool dependencies and their recursive
        runtime dependencies. The set only contains packages which
        are in the passed packages dictionary.

        :param packages: dict of name to ``_PackageDecorator``
        """
        self.depends_for_topological_order = set([])
        # skip external dependencies, meaning names that are not known packages
        deps = (self.package.build_depends +
                self.package.buildtool_depends +
                self.package.test_depends)
        for name in [d.name for d in deps if d.name in packages.keys()]:
            packages[name]._add_recursive_run_depends(
                packages, self.depends_for_topological_order)

    def _add_recursive_run_depends(
        self,
        packages,
        depends_for_topological_order
    ):
        """
        Modifies depends_for_topological_order argument by adding
        build_export/exec_depends of self recursively. Only packages
        which are in the passed packages are added and recursed into.

        :param packages: dict of name to ``_PackageDecorator``
        :param depends_for_topological_order: set to be extended
        """
        depends_for_topological_order.add(self.package.name)
        package_names = packages.keys()
        deps = (self.package.build_export_depends +
                self.package.buildtool_export_depends +
                self.package.exec_depends)
        for name in [d.name
                     for d in deps
                     if (d.name in package_names and
                         d.name not in depends_for_topological_order)]:
            packages[name]._add_recursive_run_depends(
                packages, depends_for_topological_order)


def topological_order(
    root_dir,
    whitelisted=None,
    blacklisted=None,
    underlay_workspaces=None
):
    """
    Crawls the filesystem to find packages and uses their
    dependencies to return a topologically order list.

    :param root_dir: The path to search in, ``str``
    :param whitelisted: A list of whitelisted package names, ``list``
    :param blacklisted: A list of blacklisted package names, ``list``
    :param underlay_workspaces: A list of underlay workspaces of packages
        which might provide dependencies in case of partial workspaces,
        ``list``
    :returns: A list of tuples containing the relative path and a
        ``Package`` object, ``list``
    """
    packages = find_unique_packages(root_dir)

    # find packages in underlayed workspaces
    underlay_packages = {}
    if underlay_workspaces:
        for workspace in reversed(underlay_workspaces):
            for path, package in find_unique_packages(workspace).items():
                underlay_packages[package.name] = (path, package)

    return topological_order_packages(
        packages,
        whitelisted=whitelisted,
        blacklisted=blacklisted,
        underlay_packages=dict(underlay_packages.values())
    )


def topological_order_packages(
    packages,
    whitelisted=None,
    blacklisted=None,
    underlay_packages=None
):
    """
    Topologically orders packages.

    Returns packages based on direct build/buildtool_depends and
    indirect recursive build_export/exec_depends.

    :param dict packages: A dict mapping relative paths to ``Package`` objects
    :param list whitelisted: A list of whitelisted package names
    :param list blacklisted: A list of blacklisted package names
    :param dict underlay_packages: A dict mapping relative paths to
        ``Package`` objects
    :returns: A List of tuples containing the relative path, a ``Package``
        object and a list of recursive dependencies
    :rtype: list
    """
    decorators_by_name = {}
    for path, package in packages.items():
        # skip non-whitelisted packages
        if whitelisted and package.name not in whitelisted:
            continue
        # skip blacklisted packages
        if blacklisted and package.name in blacklisted:
            continue
        packages_with_same_name = [p
                                   for p in decorators_by_name.values()
                                   if p.name == package.name]
        if packages_with_same_name:
            path_with_same_name = [p
                                   for p, v in packages.items()
                                   if v == packages_with_same_name[0]]
            raise RuntimeError("Two packages with the same name '%s' in "
                               "the workspace:\n- %s\n- %s" %
                               (package.name, path_with_same_name[0], path))
        decorators_by_name[package.name] = _PackageDecorator(package, path)

    underlay_decorators_by_name = {}
    if underlay_packages:
        for path, package in underlay_packages.items():
            # skip overlayed packages
            if package.name in decorators_by_name:
                continue
            underlay_decorators_by_name[package.name] = _PackageDecorator(
                package, path)
        decorators_by_name.update(underlay_decorators_by_name)

    # calculate transitive dependencies
    for decorator in decorators_by_name.values():
        decorator.calculate_depends_for_topological_order(decorators_by_name)

    tuples = _sort_decorated_packages(decorators_by_name)
    # remove underlay packages from result
    return [(path, package, depends)
            for path, package, depends in tuples
            if path is None or package.name not in underlay_decorators_by_name]


def _reduce_cycle_set(packages_orig):
    """
    Iteratively removes packages from a set that are not part of any cycle.

    When there is a cycle in the package dependencies,
    ``_sort_decorated_packages`` only knows the set of packages containing
    the cycle.

    :param dict packages: A dict mapping package name to
        ``_PackageDecorator`` objects
    :returns: A list of package names from the input which could not easily
        be detected as not being part of a cycle.
    :rtype: list
    """
    assert(packages_orig)
    packages = copy.copy(packages_orig)
    last_depended = None
    while len(packages) > 0:
        depended = set([])
        for name, decorator in packages.items():
            if decorator.depends_for_topological_order:
                depended = depended.union(
                    decorator.depends_for_topological_order)
        for name in list(packages.keys()):
            if name not in depended:
                del packages[name]
        if last_depended:
            if last_depended == depended:
                return packages.keys()
        last_depended = depended


def _sort_decorated_packages(packages_orig):
    """
    Sorts packages according to dependency ordering.

    When a circle is detected, a tuple with None and a string giving a
    superset of the guilty packages.

    :param dict packages: A dict mapping package name to
        ``_PackageDecorator`` objects
    :returns: A List of tuples containing the relative path, a ``Package``
        object and a list of recursive dependencies
    :rtype: list
    """
    packages = copy.deepcopy(packages_orig)

    ordered_packages = []
    while len(packages) > 0:
        # find all packages without build dependencies
        names = []
        for name, decorator in packages.items():
            if not decorator.depends_for_topological_order:
                names.append(name)
        if not names:
            # in case of a circular dependency pass a string with
            # the names list of remaining package names, with path
            # None to indicate cycle
            ordered_packages.append(
                [None, ', '.join(sorted(_reduce_cycle_set(packages))), None])
            break

        # alphabetic order only for convenience
        names.sort()

        # add first candidates to ordered list
        # do not add all candidates since removing the depends from
        # the first might affect the next candidates
        name = names[0]
        ordered_packages.append([
            packages[name].path,
            packages[name].package,
            packages_orig[name].depends_for_topological_order])
        # remove package from further processing
        del packages[name]
        for package in packages.values():
            if name in package.depends_for_topological_order:
                package.depends_for_topological_order.remove(name)
    return ordered_packages
