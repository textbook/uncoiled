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
