Scopes
======

Every component has a lifecycle scope that controls how instances are cached.

Singleton (default)
-------------------

One instance per container lifetime.  Created on first access, reused
thereafter:

.. code-block:: python

   from uncoiled import component, Scope

   @component  # scope=Scope.SINGLETON is the default
   class DatabasePool:
       ...

Transient
---------

A new instance on every resolution --- nothing is cached:

.. code-block:: python

   @component(scope=Scope.TRANSIENT)
   class RequestHandler:
       ...

Request
-------

One instance per HTTP request.  Requires
:class:`~uncoiled.fastapi.RequestScopeMiddleware` (or manual use of
:meth:`~uncoiled.Container.request_context`):

.. code-block:: python

   @component(scope=Scope.REQUEST)
   class UserController:
       def __init__(self, repo: UserRepository, tenant: TenantId) -> None:
           ...

Request-scoped values are isolated via ``contextvars``, so concurrent requests
each get their own instance.

Auto
----

Infers the scope from the dependency graph instead of requiring an explicit
declaration.  Opt in with ``scope=Scope.AUTO``:

.. code-block:: python

   @component(scope=Scope.AUTO)
   @dataclass
   class UserController:
       repo: UserRepository       # singleton
       tenant: TenantId           # request-scoped

Because ``TenantId`` is request-scoped, the container resolves
``UserController`` as request-scoped --- the only valid choice.

Resolution rules:

- Any dependency is **request-scoped** → component becomes ``REQUEST``.
- All dependencies are **singleton** (or transient, or none) → component
  becomes ``SINGLETON``.
- **Transient** dependencies are transparent --- they don't force the parent
  to any particular scope.
- Resolution is **transitive**: if ``A(AUTO)`` depends on ``B(AUTO)`` which
  depends on ``C(REQUEST)``, both ``A`` and ``B`` become ``REQUEST``.
- Mutual ``AUTO`` dependencies that cannot be resolved produce an
  ``AUTO_CYCLE`` validation error.

``Scope.AUTO`` works on both ``@component`` and ``@factory``.  The default
scope remains ``Scope.SINGLETON`` --- ``AUTO`` is always opt-in.

Scope Validation
----------------

The dependency graph validates scope compatibility eagerly.  A singleton
depending on a request-scoped component is rejected:

.. code-block:: text

   Singleton 'CachedService' depends on request-scoped 'TenantId' ---
   singletons cannot depend on request-scoped components because they
   are created at startup before any request context exists.

Lifecycle Hooks
---------------

Register init and destroy methods to run during
:meth:`~uncoiled.Container.start` / :meth:`~uncoiled.Container.close`:

.. code-block:: python

   c.register(
       ConnectionPool,
       init_method="connect",
       destroy_method="disconnect",
   )

   with c:  # calls start() on enter, close() on exit
       pool = c.get(ConnectionPool)
       # pool.connect() was called

Generator factories handle cleanup automatically:

.. code-block:: python

   @factory
   def create_session(pool: ConnectionPool) -> Session:
       session = pool.checkout()
       yield session
       session.close()
