Logging
=======

Uncoiled logs framework activity under the ``"uncoiled"`` logger.  All
messages use the ``DEBUG`` level by default, so they are silent unless you
opt in.

Enabling debug output
---------------------

.. code-block:: python

   import logging

   logging.getLogger("uncoiled").setLevel(logging.DEBUG)
   logging.basicConfig()

You will then see messages such as::

   DEBUG:uncoiled:Registered component UserService (scope=singleton, qualifier=None)
   DEBUG:uncoiled:Container starting (3 registrations)
   DEBUG:uncoiled:Created UserRepository (scope=singleton, qualifier=None)
   DEBUG:uncoiled:Calling ConnectionPool.connect()
   DEBUG:uncoiled:Container started

What is logged
--------------

- **Registration** — every ``register()``, ``register_factory()``,
  ``register_instance()`` call, including scope and qualifier.
- **Scanning** — module name when ``scan()`` is called.
- **Startup / shutdown** — ``start()`` and ``close()`` with instance counts.
- **Instance creation** — type, scope, and qualifier each time a new
  component is created (cache hits are silent).
- **Lifecycle hooks** — ``init_method`` and ``destroy_method`` calls.
- **AUTO scope inference** — the resolved scope for each ``Scope.AUTO``
  component.
- **Overrides and forks** — ``override()`` and ``fork()`` calls.

Warnings
--------

A small number of conditions emit ``WARNING``-level messages:

- ``DotEnvSource`` or ``YamlSource`` given a path that does not exist.
- A ``list[T]`` dependency resolves to an empty list (no matching
  implementations registered).
