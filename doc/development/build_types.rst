``ament`` Build Types
=====================

The concept of "Build Types", sometimes referred to as ``build_type``, allows the ament build tools to adapt to non-ament types of packages.
For example, though the default ``build_type`` for a package is ``ament_cmake``, you could also declare it to be ``cmake`` or ``python``.
This would indicate that the package is not a traditional CMake based ``ament`` package, but instead it should be handled differently.
For a package with a ``build_type`` of plain ``cmake``, the ``ament build_pkg`` command will treat it differently than an ``ament_cmake`` typed package.
This also allows you to build workspaces with non-homogeneous types of packages using the ``ament build`` command, because for each package in the workspace it will follow the predefined build/install pattern for that package's ``build_type``.

Adding build support for new ``build_type``'s
---------------------------------------------

The :py:mod:`ament_tools.build_type` module provides a partially abstract base class, :py:class:`ament_tools.build_type.BuildType`, from which a new class can be derived in order to add support for additional ``build_type``'s.

.. autoclass:: ament_tools.build_type.BuildType

The text diagram below shows the list of operations which take place in order of operation.

.. code::

    BuildType        |                       time | o = optional
    Sequence         |                        |   | e = external to BuildType
                     |                        V   |
    Input            | Function                   | Output
    --------------------------------------------------------------------------
    parser, [args]   | prepare_arguments      (o) | parser
    --------------------------------------------------------------------------
    args             | argument_preprocessor  (o) | args, extra_opts
    --------------------------------------------------------------------------
    parser, args     | parse_args             (e) | opts
    --------------------------------------------------------------------------
    opts, extra_opts | extend_context         (o) | context_ext
    --------------------------------------------------------------------------
    default_context  | on_build                   |
    + context_ext    |                            |
    --------------------------------------------------------------------------
    default_context  | on_install                 |
    + context_ext    |                            |

Some of the operations are external, shown here for your edification of the process and others are optional.
First the functions related to command line processing are called to allow the developer to hook into the command line interface and the argument processing.
Then the ``on_build`` and ``on_install`` methods are called to execute the build and install of the package, respectively.

The command line processing related functions (``prepare_arguments``, ``argument_preprocessor``, ``parse_args``, and ``extend_context``) are called once per invocation of the command, i.e., either ``ament build`` or ``ament build_pkg``.
However, the build processing related functions (``on_build`` and ``on_install``) are called once for each package.

Command Line Processing
^^^^^^^^^^^^^^^^^^^^^^^

This interface allows you to have command line options for both the ``ament build`` and ``ament build_pkg`` commands, as well as any other commands which choose to utilize this interface.
The pattern for how command line arguments can be injected is similar to the way it works for the "Verb Pattern" as described in :py:mod:`osrf_pycommon.cli_utils.verb_pattern`.

First a ``prepare_arguments`` function is called with parameters for the :py:class:`argparse.ArgumentParser` and optionally the current command line arguments, likely extracted from ``sys.argv``.

.. automethod:: ament_tools.build_type.BuildType.prepare_arguments

Using the given parser inside this method you can add arguments to the command line using the ``add_argument`` method of the parser.
Finally, you should return the modified parser.
Then, as long as ``--help`` was not invoked, the process continues by calling the provided ``argument_preprocessor`` if it was provided.

The ``argument_preprocessor`` gives the opportunity to manipulate the arguments before they are passed to the parser's ``parse_args`` method.

.. automethod:: ament_tools.build_type.BuildType.argument_preprocessor

This is sometimes necessary when ``argparse`` is not sophisticated enough to extract the arguments correctly.
Once you can modified the arguments, you can return the modified arguments and any extra options as a dictionary.

As an example, imagine we are adding support for plain ``cmake``, our subclass might look like this so far:

.. code:: python

    from ament_tools.build_type import BuildType

    class CMakeBuildType(BuildType):
        ...

        def prepare_arguments(parser):
            parser.add_argument('--force-cmake', action='store_true',
                                help="Force invocation of cmake")
            parser.add_argument(
                '--cmake-args',
                nargs='*',
                default=[],
                help='Arbitrary arguments which are passed to CMake. '
                     'It must be passed after other arguments since it collects all '
                     'following options.')
            return parser

        def argument_preprocessor(args):
            extra_opts = {}
            # Extract the cmake args, argparse cannot do it correctly
            if '--cmake-args' not in args:
                return args, extra_opts
            index = args.index('--cmake-args')
            args, extra_opts['cmake_args'] = args[:index], args[index + 1:]
            return args, extra_opts

In this example some arguments are added in the ``prepare_arguments`` method and special argument extraction is done for one of the arguments in the ``argument_preprocessor`` method.

The final step of argument processing is to convert, if desired, any parsed options into a context extender (:py:class:`ament_tools.context.ContextExtender`).

.. autoclass:: ament_tools.context.ContextExtender
    :members:

A context extender is used to extend the context provided by the parent command, e.g. the ``ament build`` command.
The context is what is passed to methods like ``on_build`` and ``on_install`` at a later point in the build process.
The context is an opportunity to consolidate the parsed command line options, and any other sources of configuration, into a single, consistent configuration for use by the later tasks.
The context is represented by the :py:class:`ament_tools.context.Context` class.

.. autoclass:: ament_tools.context.Context

The context extender encapsulates "context extensions", which fall into one of three types: add, replace, or extend.
Using these extension expressions your custom :py:class:`BuildType` can extend the context object provided to ``on_build`` and ``on_install``.

Package Build Processing
^^^^^^^^^^^^^^^^^^^^^^^^

After argument parsing and configuration have been handled, the ``on_build`` and ``on_install`` functions are called to build and then install a package, respectively.
Passed to these functions is the build :py:class:`Context` object, which has optionally been extended by your custom :py:class:`BuildType` implementation.

In all cases the context contains some common configurations which need to be utilized by all build types and some other common options which may not be used by all build types, but is used by many of them.
This is a list of the configurations which are provided by default in the build Context object:

- ``source_space``: This is the absolute path to the root of the source code for this package, directly under this should be the package's manifest file (``package.xml``).
- ``package_manifest``: This is the object representation of the package manifest (:py:class:`catkin_pkg.package.Package`) for this package. This is set for every package, so changing it will not affect other packages.
- ``build_space``: This is the absolute path to the root of the build folder for this package, it is not guaranteed to exist yet, but it is guaranteed to be unique to this package for this build (file operations need not be atomic).
- ``install_space``: This is the target location for the installation step, this would map directly to the ``CMAKE_INSTALL_PREFIX``. This value may or may not be shared with other packages. Therefore file operations in this location should be atomic if possible, and they should be aware that other packages could possibly overwrite files installed by this package at any time.
- ``install``: This is ``True`` if the installation of the package should be carried out, if ``False`` then the package should only be built if that distinction is possible. If there is no build step separate from the install step, then nothing should be done when this is ``False``.
- ``isolated_install``: This is ``False`` by default which means packages in the same workspace will all install to the same root ``install_space``. When this is ``True`` each package will get its own unique ``install_space``.
- ``symbolic_link_install``: When this is ``True``, the package should be installed in a "developer" mode if possible where source files and resources are linked into the install space rather than copied.
- ``dry_run``: True if this is a dry run of the build/install process.
- ``make_flags``: This is a list of flags for ``make``. Not all build types will use these flags, but they might be things like ``-jN`` which set the parallelization level of ``make``. This does not include things like ``make`` targets which would be more like "``make`` options", i.e. flags != options.

In addition to these default set of configurations, your custom BuildType can add more configurations, extend these configurations, or even replace these configurations.
If you do not intend to extend or replace existing configurations, it is recommended to use ``add`` and a name-space.
For example, if both the vanilla ``cmake`` build type and the ``ament_cmake`` have the ability to specify "CMake arguments", then they might either choose to extend a common configuration like ``cmake_arguments`` or they may choose to name-space them as ``cmake_arguments`` and ``ament_cmake_arguments``, or both.

The ``on_build`` method of your custom BuildType interface class is required to override the built-in one.
The only parameter to ``on_build`` is the build Context which has been extended with any ``ContextExtender``'s provided by ``extend_context``.

The ``on_build`` and ``on_install`` functions can ``yield`` :py:class:`ament_tools.build_type.BuildAction` objects if desired.
These ``BuildAction`` objects will be automatically processed in a consistent way.

.. autoclass:: ament_tools.build_type.BuildAction

This class allows you to choose between providing commands to be executed with subprocess or a callable functor, and it allows you to specify a dry run behavior for you action.
By default if you do not specify a ``dry_run_cmd`` for the dry run behavior then nothing is done on dry run.
For example, this might be the implementation of the ``on_build`` function for the ``python`` ``build_type``:

.. code-block:: python

    class PythonBuildType(BuildType):
        on_build(context):
            cmd = [which('python'), os.path.join(context.source_space, 'setup.py'), 'build']
            yield BuildAction(cmd)

If you do not give an explicit title, then one is generated based on the command or the function given.

The ``on_build`` and ``on_install`` functions are not required to ``yield`` ``BuildAction``'s, instead this pattern just offers a convenient and consistent way to execute your actions.
Sometimes this method is not flexible enough, e.g. you need to check the return type of a command and do something based on it.
However, if you do not use the "yielding BuildActions" pattern then you need to take special care to print and run the commands in a standard way.
