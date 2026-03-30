Components and Factories
========================

``@component``
--------------

The :func:`~uncoiled.component` decorator marks a class for constructor
injection.  The container inspects the class's ``__init__`` to discover
dependencies:

.. code-block:: python

   from uncoiled import component, Scope

   @component
   class UserService:
       def __init__(self, repo: UserRepository) -> None:
           self.repo = repo

   @component(scope=Scope.TRANSIENT)
   class RequestHandler:
       def __init__(self, service: UserService) -> None:
           self.service = service

   @component(provides=UserRepository)
   class PostgresRepository:
       def __init__(self, config: DbConfig) -> None:
           ...

Dataclasses work naturally as components --- their generated ``__init__`` is
introspected like any other:

.. code-block:: python

   from dataclasses import dataclass

   @component(scope=Scope.REQUEST)
   @dataclass
   class UserController:
       repo: UserRepository
       tenant: TenantId

Options:

- ``scope`` --- lifecycle scope (default: ``Scope.SINGLETON``)
- ``qualifier`` --- disambiguate multiple implementations of the same type
- ``provides`` --- register under an interface type instead of the concrete class

``@factory``
------------

The :func:`~uncoiled.factory` decorator marks a function or classmethod as a
factory.  Dependencies are introspected from the function's parameters, and the
return type annotation determines the provided type:

.. code-block:: python

   from uncoiled import factory

   @factory
   def create_client(config: HttpConfig) -> HttpClient:
       return HttpClient(timeout=config.timeout)

Factory classmethods work with either decorator ordering:

.. code-block:: python

   class SqliteRepository:
       def __init__(self, conn: sqlite3.Connection) -> None:
           self._conn = conn

       @classmethod
       @factory
       def create(cls, config: DbConfig) -> UserRepository:
           conn = sqlite3.connect(config.url)
           return cls(conn)

Use ``provides=`` to override the return annotation when the interface differs
from the concrete type.

Scanning
--------

:meth:`~uncoiled.Container.scan` discovers all ``@component`` and ``@factory``
decorations in a module and its subpackages:

.. code-block:: python

   c = Container()
   c.scan("myapp")          # by module name
   c.scan(myapp.infra)      # by module object

Manual Registration
-------------------

For types you don't control, register them imperatively:

.. code-block:: python

   c.register(ThirdPartyService)
   c.register_instance(existing_object)
   c.register_factory(create_session, return_type=Session)

Qualifiers
----------

When multiple implementations of the same type exist, use
:class:`~uncoiled.Qualifier` to disambiguate:

.. code-block:: python

   from typing import Annotated
   from uncoiled import Qualifier

   @component(qualifier="primary")
   class PrimaryDb(Database):
       ...

   @component(qualifier="replica")
   class ReplicaDb(Database):
       ...

   class Service:
       def __init__(
           self,
           db: Annotated[Database, Qualifier("primary")],
       ) -> None:
           self.db = db

Optional and List Dependencies
------------------------------

Optional dependencies resolve to ``None`` when not registered:

.. code-block:: python

   class Service:
       def __init__(self, cache: Cache | None = None) -> None:
           self.cache = cache

List dependencies collect all implementations of a type, including
registered subclasses:

.. code-block:: python

   class EventBus:
       def __init__(self, handlers: list[EventHandler]) -> None:
           self.handlers = handlers

If ``EventHandler`` is a base class and ``AuditHandler``,
``LoggingHandler`` are registered as subclasses, the bus receives
both.  The same resolution is available imperatively via
:meth:`~uncoiled.Container.get_all`:

.. code-block:: python

   handlers = container.get_all(EventHandler)  # [AuditHandler(), LoggingHandler()]

When combined with a qualifier, only implementations registered with that
qualifier are returned:

.. code-block:: python

   class Pipeline:
       def __init__(
           self,
           steps: Annotated[list[Step], Qualifier("pre")],
       ) -> None:
           self.steps = steps  # only Steps with qualifier="pre"

List dependencies are never validated as missing --- an empty list is
returned when no matching implementations are registered.

Environment Variables
---------------------

:class:`~uncoiled.EnvVar` injects values directly from the environment:

.. code-block:: python

   from typing import Annotated
   from uncoiled import EnvVar

   class Service:
       def __init__(
           self,
           db_url: Annotated[str, EnvVar("DATABASE_URL")] = ":memory:",
       ) -> None:
           self.db_url = db_url

Supported coercion types: ``str``, ``int``, ``float``, ``bool``, ``Path``.

Logger Injection
----------------

``logging.Logger`` is auto-injected without registration, named after the
component's module:

.. code-block:: python

   import logging

   @component
   class Service:
       def __init__(self, logger: logging.Logger) -> None:
           self.logger = logger
       # logger.name == "myapp.service"

Register a ``Logger`` explicitly to override auto-injection.
