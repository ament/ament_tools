``ament`` Command Line Tools
============================

.. toctree::
   :hidden:

This Python package provides command line tools for working with ament packages and ament workspaces.

The ``ament`` command
----------------------

The ``ament`` Command-Line Interface (CLI) tool is the single point of entry for most of the functionality provided by this package.
All invocations of the ``ament`` CLI tool take this form:

.. code-block:: bash

    $ ament [global options] <verb> [verb arguments and options]

The ``ament`` CLI tool requires that you provide a verb.
The verbs could be many things, like ``build`` which builds a ament workspace or ``list`` which simply lists the ament packages found in one or more folders.
Optionally, global options can be provided before the verb, things like ``-d`` for debug level verbosity or ``-h`` for help on the ``ament`` CLI tool itself.
Verbs can take arbitrary arguments and options, but they must all come after the verb.
For more help on a particular verb, simply pass ``-h`` or ``--help`` after the verb.
