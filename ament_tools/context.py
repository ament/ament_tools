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


class Context(dict):
    """Encapsulate a set of configurations for a particular context.

    This is used by the build and build_pkg verbs, for example, to encapsulate
    the build configurations like build space location, and whether or not to
    install.

    The Context can be extended by setting attributes directly, but a
    :py:class:`ContextExtender` can be used to modify a Context using a
    defined pattern, one of: add, replace, or extend.
    This prevents every actor who modifies a Context from reimplementing the
    boilerplate for these patterns.

    You can access members of the Context as a dictionary and/or as an object:

    .. code:: python

        >>> c = Context()
        >>> c['foo'] = 'bar'
        >>> print(c['foo'])
        bar
        >>> print(c.foo)
        bar
        >>> c.ping = 'pong'
        >>> print(c.ping)
        pong
        >>> print(c['ping'])
        pong

    The object attribute based access makes it more convenient to access
    configurations and the dictionary style access makes it more convenient to
    programatically extend.
    """

    def __init__(self, *args):
        dict.__init__(self, args)

    def __str__(self):
        lines = []
        max_key_length = str(max([len(k) for k in self.keys()]))
        for k, v in self.items():
            lines.append(("{0:<" + max_key_length + "} => {1}").format(k, v))
        return "\n".join(lines)

    def __getattribute__(self, name):
        if name in list(dict.keys(self)):
            return self[name]
        return dict.__getattribute__(self, name)

    def __setattr__(self, name, value):
        self[name] = value


class ContextExtender(object):
    """Store a series of extensions for a Context which can be applied later.

    This can be used to describe a series of extensions (add, replace,
    or extend) which can later be applied to a Context.
    This decouples the intent of the changes from the actual changes, allowing
    different sources of changes which may conflict to be resolved later by
    a common actor with access to the Context and all ContextExtender's.

    In the context of the BuildType concept, this is used to allow a BuildType
    interface to describe how it would like to alter the build Context without
    giving it direct access.
    This is important to prevent accidental cross talk between providers of
    Context extensions.

    This is a typical example of how you might use a ContextExtender:

    .. code:: python

        >>> from ament_tools.context import Context
        >>> from ament_tools.context import ContextExtender
        >>> c = Context()
        >>> ce = ContextExtender()
        >>> ce.add('foo', 'bar')
        >>> # You cannot add an items a second time (add must be a new key)
        >>> ce.add('foo', 'cant add this a second time!')
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
          File "ament_tools/context.py", line 137, in add
            "Context key '{0}' will already exist.".format(key)
        ament_tools.context.ContextAddExtensionException: Context key 'foo' will already exist.
        >>> ce.replace('foo', 'bar2')
        >>> ce.extend('foo', 'bar3')
        >>> ce.extensions
        [['add', 'foo', 'bar'], ['replace', 'foo', 'bar2'], ['extend', 'foo', 'bar3']]
        >>> ce.apply_to_context(c)
        >>> c.items()
        [('foo', 'bar2bar3')]

    You must also make sure extend is called with compatible value types:

    .. code:: python

        >>> ce2 = ContextExtender()
        >>> ce2.extend('foo', ['bar4'])
        >>> ce2.apply_to_context(c)
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
          File "ament_tools/context.py", line 119, in apply_to_context
            context[key] += value
        TypeError: cannot concatenate 'str' and 'list' objects

    In the above case this error happens because the current value for ``foo``
    is a ``str``, but the value given for the ``extend`` action is a ``list``.
    """

    def __init__(self):
        self.__extensions = []

    @property
    def extensions(self):
        return self.__extensions

    def apply_to_context(self, context):
        """Apply extensions to given context.

        Iterates through extensions (add, replace, extend) in the order they
        were added and tries to apply them to the given context.

        This can fail if the add extension has been used or if there is type
        difference problem when using the extend extension.

        :param context: Context object to which the extensions are applied
        :type context: :py:class:`Context`
        :raises: ContextAddExtensionException when an add extension fails
        :raises: TypeError when an extend extension fails due to incompatible
            types, e.g. cannot add (+=) a string to a list.
        """
        for action, key, value in self.__extensions:
            assert action in ['add', 'replace', 'extend']
            if action == 'add':
                if key in list(context.keys()):
                    raise ContextAddExtensionException(
                        "Context pair '{0}:{1}' cannot be added because the "
                        "pair '{2}:{3}' already exists in the context."
                        .format(key, value, key, context[key]))
                context[key] = value
            elif action == 'replace':
                context[key] = value
            elif action == 'extend':
                if key in list(context.keys()):
                    context[key] += value
                else:
                    context[key] = value

    def add(self, key, value):
        """Extend Context by adding the key and value.

        This will fail immediately if there is already an extension for
        this key.

        This will fail on application to the context if the key already
        exists in the context.

        :raises: ContextAddExtensionException when key cannot be added without
            replacing an existing key.
        """
        if [ex for ex in self.__extensions if ex[1] == key]:
            raise ContextAddExtensionException(
                "Context key '{0}' will already exist.".format(key)
            )
        self.__extensions.append(['add', key, value])

    def replace(self, key, value):
        """Extend Context by replacing, if necessary, the key and value.

        If other extensions exist for this key, then they will replaced in the
        order in which they were added.

        If the key already exists in the Context, it will be replaced by this
        key and value pair.
        """
        self.__extensions.append(['replace', key, value])

    def extend(self, key, value):
        """Extend Context by extending the existing value, otherwise add.

        If the key does not exist in the Context, then this key and value pair
        are added to the Context, otherwise the existing value is extended
        with this value.

        If the key already exists in the Context, but the type is different,
        e.g. str vs list, then this can fail on application to the Context.
        """
        self.__extensions.append(['extend', key, value])


class ContextAddExtensionException(Exception):
    pass
