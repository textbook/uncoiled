uncoiled
========

Dependency injection for modern Python.

Uncoiled is a dependency injection framework that resolves dependencies from
``__init__`` type annotations --- no markers, no framework imports in your
business code.

.. code-block:: python

   from uncoiled import Container, component

   class UserRepository:
       pass

   @component
   class UserService:
       def __init__(self, repo: UserRepository) -> None:
           self.repo = repo

   c = Container()
   c.register(UserRepository)
   c.scan(__import__(__name__))
   c.start()

   service = c.get(UserService)
   assert isinstance(service.repo, UserRepository)

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   getting-started
   guide/components
   guide/configuration
   guide/scopes
   guide/testing
   guide/fastapi

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/container
   api/decorators
   api/configuration
   api/errors
