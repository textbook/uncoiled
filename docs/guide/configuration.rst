Configuration
=============

Uncoiled provides a layered configuration system inspired by Spring Boot.

Config Properties
-----------------

Bind a prefix to a frozen dataclass with
:func:`~uncoiled.config_properties`:

.. code-block:: python

   from dataclasses import dataclass
   from uncoiled import config_properties

   @config_properties("db")
   @dataclass(frozen=True)
   class DbConfig:
       host: str = "localhost"
       port: int = 5432
       url: str = ":memory:"

Then bind it from a source at startup:

.. code-block:: python

   from uncoiled import EnvSource, bind_config, Container

   config = bind_config(DbConfig, EnvSource())
   c = Container()
   c.register_instance(config)

With ``DB_HOST=postgres`` in the environment, ``config.host`` resolves to
``"postgres"`` and ``config.port`` uses its default ``5432``.

Configuration Sources
---------------------

All sources implement the :class:`~uncoiled.ConfigSource` protocol:

:class:`~uncoiled.DictSource`
   In-memory dictionary.

:class:`~uncoiled.EnvSource`
   Reads from environment variables. Tries the normalised key first, then the
   uppercase/underscore form (``db.host`` -> ``DB_HOST``).

:class:`~uncoiled.DotEnvSource`
   Parses a ``.env`` file. Handles quoted values.

:class:`~uncoiled.YamlSource`
   Reads a YAML file (requires ``uncoiled[yaml]``). Nested keys are flattened
   with dots.

:class:`~uncoiled.LayeredSource`
   Chains multiple sources with first-match-wins precedence:

   .. code-block:: python

      from uncoiled import LayeredSource, EnvSource, DotEnvSource, YamlSource

      source = LayeredSource(
          EnvSource(),
          DotEnvSource(".env"),
          YamlSource("config.yml"),
      )

Relaxed Binding
---------------

Keys are normalised so that all of these refer to the same value:

- ``db.host``
- ``DB_HOST``
- ``db-host``

Profiles
--------

Set ``UNCOILED_PROFILES=dev,local`` to activate profiles.  Use
:func:`~uncoiled.get_active_profiles` to conditionally register components:

.. code-block:: python

   from uncoiled import get_active_profiles

   profiles = get_active_profiles()
   if "dev" in profiles:
       c.register(MockMailer, provides=Mailer)
   else:
       c.register(SmtpMailer, provides=Mailer)
