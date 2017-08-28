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

import os

from .context import ContextExtender

IS_WINDOWS = os.name == 'nt'


class BuildAction:
    """
    Represent an action to do at build time, either a command or a functor.

    These objects are yielded from the ``on_*`` methods in the BuildType class
    for a particular ``build_type``.

    The constructor for this class takes a cmd, a type, optionally a title,
    optionally a dry run cmd, optionally a different current working directory
    (``cwd``), and optionally different environment variables (``env``).

    The cmd (command) is either a list of arguments as strings which is meant
    to be executed as a subprocess, or a callable Python object like
    a function or a method of an object.

    The type parameter indicates the type of the action.
    Currently the possible values for this are either ``command`` or
    ``function``.

    The title (optional) is used when logging the action.

    There is also an optional parameter to the constructor, ``dry_run_cmd``
    which defaults to None.
    This parameter can be used to provide an alternative cmd for the
    dry run case, e.g. ``['git', 'push']`` might become
    ``['git', 'push', '--dry-run']``.

    The default working directory for commands is the build space which can be
    overridden with the optional ``cwd`` parameter.

    The environment used when running the command can be overridden using the
    the optional ``env`` parameter.
    """

    def __init__(self, cmd, type='command', title=None, dry_run_cmd=None,
                 cwd=None, env=None):
        self.cmd = cmd
        self.type = self.__validate_type(type, cmd, dry_run_cmd)
        self.title = title
        self.dry_run_cmd = dry_run_cmd
        self.cwd = cwd
        self.env = env

    def __validate_type(self, type_str, cmd, dry_run_cmd):
        if type_str not in ['command', 'function']:
            raise ValueError("Invalid BuildAction type '{0}'".format(type_str))
        if cmd is None:
            return type_str
        if type_str == 'command' and not hasattr(cmd, '__iter__'):
            raise ValueError("BuildAction cmd is expected to be list or tuple "
                             "when type is 'command', got '{0}' of type "
                             "'{1}' instead.".format(cmd, type(cmd)))
        if type_str == 'function' and not callable(cmd):
            raise ValueError("BuildAction cmd is expected to be callable "
                             "when type is 'function', but '{0}' is not "
                             "callable.".format(cmd))
        if dry_run_cmd is None:
            return type_str
        if type_str == 'command' and not hasattr(dry_run_cmd, '__iter__'):
            raise ValueError("BuildAction dry_run_cmd is expected to be list "
                             "or tuple when type is 'command', got '{0}' of "
                             "type '{1}' instead."
                             .format(dry_run_cmd, type(dry_run_cmd)))
        if type_str == 'function' and not callable(dry_run_cmd):
            raise ValueError("BuildAction cmd is expected to be callable "
                             "when type is 'function', but '{0}' is not "
                             "callable.".format(dry_run_cmd))
        return type_str


class DefaultBuildTypeLogger:
    def info(self, *args):
        print(*args)

    def warn(self, *args):
        print(*args)


class BuildType:
    """
    Base class interface for building a ``build_type`` with ament tools.

    This class provides an interface for how to handle building of ament
    ``build_type``'s, but it cannot be used as is and requires subclassing.

    When subclassing this class, the only functions which raise a
    :py:exc:`NotImplementedError` by default are :py:meth:`on_build`,
    :py:func:`on_test`, :py:func:`on_install` and :py:func:`on_uninstall`.
    Therefore those functions need to be overridden.
    """

    build_type = None
    """
    Build type identification string.

    This should be set by the subclass and should match the ``built_type``
    set in the package manifest of applicable packages.
    """

    description = None
    """
    Description of this build type.

    This should be set by the subclass.
    """

    logger = DefaultBuildTypeLogger()
    """Logging singleton, allows executor to hook in a custom logger."""

    def prepare_arguments(self, parser):
        """
        Add BuildType specific arguments to the command line options.

        Override this function to extend the command line arguments using the
        provided argparse ArgumentParser.
        Also, be sure to return the parser you were given.

        For example:

        .. code:: python

            class MyBuildType(BuildType):
                def prepare_arguments(self, parser):
                    parser.add_argument('--arg', help="My new argument")
                    return parser

        Overriding this method is optional, by default it simply returns the
        parser unchanged.

        :param parser: argparse ArgumentParser to which arguments can be added.
        :type parser: :py:class:`argparse.ArgumentParser`
        :returns: The given parser.
        :rtype: :py:class:`argparse.ArgumentParser`
        """
        return parser

    def argument_preprocessor(self, args):
        """
        Process arguments before being processed with argparse.

        Override this function to perform preprocessing on the arguments
        before they are passed to argparse.
        This is sometimes necessary when argparse is not clever enough to
        handle your arguments.
        """
        extra_opts = {}
        return args, extra_opts

    def extend_context(self, opts):
        """
        Convert arguments into a ContextExtender object.

        Override this function to be able to convert resulting options from
        argparse into a ContextExtender object which will be used to extend
        the build Context object given to the ``on_build``, ``on_test`` and
        ``on_install`` methods.

        :param opts: options from argparse, already extended with extra options
            from the ``argument_preprocessor``.
        :type opts: :py:class:`argparse.Namespace`
        :returns: A ContextExtender object.
        :rtype: :py:class:`ament_tools.context.ContextExtender`
        """
        return ContextExtender()

    def on_build(self, context):
        raise NotImplementedError

    def on_test(self, context):
        raise NotImplementedError

    def on_install(self, context):
        raise NotImplementedError

    def on_uninstall(self, context):
        raise NotImplementedError

    def info(self, *args):
        """Log informational messages for this build."""
        self.logger.info(*args)

    def warn(self, *args):
        """Log warning messages for this build."""
        self.logger.warn(*args)

    def _get_command_prefix(
        self, build_type, name, context, *,
        additional_dependencies=None, additional_lines=None
    ):
        if additional_dependencies is None:
            additional_dependencies = []
        return get_command_prefix(
            '%s__%s' % (build_type, name),
            context.build_space,
            dependencies=context.build_dependencies + additional_dependencies,
            additional_lines=additional_lines)


def get_command_prefix(
    generated_filename, build_space, dependencies, additional_lines=None
):
    lines = []
    if not IS_WINDOWS:
        lines.append('#!/usr/bin/env sh\n')
        extension = 'sh'
    else:
        lines.append('@echo off\n')
        extension = 'bat'

    for path in dependencies:
        local_setup = os.path.join(path, 'local_setup.%s' % extension)
        if not IS_WINDOWS:
            lines.append('if [ -n "$AMENT_TRACE_SETUP_FILES" ]; then')
            lines.append('  echo ". \\"%s\\""' % local_setup)
            lines.append('fi')
            lines.append('if [ -f "%s" ]; then' % local_setup)
            lines.append('  . "%s"' % local_setup)
            lines.append('fi')
        else:
            lines.append(
                'if "%AMENT_TRACE_SETUP_FILES%" NEQ "" echo call "{0}"'.format(local_setup))
            lines.append('if exist "{0}" call "{0}"'.format(local_setup))
        lines.append('')

    lines.extend(additional_lines or [])

    if IS_WINDOWS:
        lines.append('%*')
        lines.append('if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%')

    generated_file = os.path.join(
        build_space, '%s.%s' % (generated_filename, extension))
    with open(generated_file, 'w') as h:
        for line in lines:
            h.write('%s\n' % line)

    if not IS_WINDOWS:
        return ['.', generated_file, '&&']
    else:
        return [generated_file]
