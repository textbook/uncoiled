FastAPI Integration
===================

Install with ``pip install uncoiled[fastapi]``.

Inject[T]
---------

Use ``Inject[T]`` in route signatures to resolve from the container:

.. code-block:: python

   from uncoiled.fastapi import Inject

   @app.get("/users")
   def list_users(controller: Inject[UserController]):
       return controller.list_all()

This is a type alias for ``Annotated[T, Depends(...)]`` --- FastAPI handles it
natively.

Application Setup
-----------------

Wire the container into a FastAPI app using the lifespan and middleware:

.. code-block:: python

   from fastapi import FastAPI
   from uncoiled import Container, EnvSource, bind_config
   from uncoiled.fastapi import (
       RequestScopeMiddleware,
       RequestValueProvider,
       uncoiled_lifespan,
   )

   def create_app() -> FastAPI:
       c = Container()
       c.register_instance(bind_config(DbConfig, EnvSource()))
       c.scan("myapp")

       app = FastAPI(lifespan=uncoiled_lifespan(c))
       app.add_middleware(
           RequestScopeMiddleware,
           container=c,
           request_values=[
               RequestValueProvider(
                   TenantId,
                   lambda r: TenantId(r.headers["x-tenant-id"]),
               ),
           ],
       )
       return app

Request Values
--------------

:class:`~uncoiled.fastapi.RequestValueProvider` extracts values from each HTTP
request and seeds them into the request scope:

.. code-block:: python

   RequestValueProvider(
       TenantId,
       lambda request: TenantId(request.headers.get("x-tenant-id", "default")),
   )

These values are then injectable into request-scoped components via normal
constructor injection.

Testing
-------

Pass a test container to the app factory so tests use the same routes and
middleware:

.. code-block:: python

   def test_app():
       c = Container()
       c.scan("myapp")
       c.register(MockRepo, provides=UserRepository, replace=True)
       app = create_app(c)
       # use httpx.AsyncClient with ASGITransport
