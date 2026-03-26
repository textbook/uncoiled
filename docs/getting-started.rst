Getting Started
===============

Installation
------------

.. code-block:: bash

   pip install uncoiled

For optional integrations:

.. code-block:: bash

   pip install uncoiled[fastapi]   # FastAPI support
   pip install uncoiled[yaml]      # YAML config sources

Core Concepts
-------------

Uncoiled wires dependencies by inspecting ``__init__`` signatures.  Your
classes never import the framework --- they just declare what they need via
standard type annotations.

**Container** manages registration, validation, and resolution:

.. code-block:: python

   from uncoiled import Container

   c = Container()
   c.register(UserRepository)
   c.register(UserService)
   c.start()

   service = c.get(UserService)

**@component** marks a class for automatic discovery via ``scan()``:

.. code-block:: python

   from uncoiled import component

   @component
   class UserService:
       def __init__(self, repo: UserRepository) -> None:
           self.repo = repo

   c = Container()
   c.scan("myapp")  # discovers all @component classes
   c.start()

**@factory** marks a function or classmethod as a factory:

.. code-block:: python

   from uncoiled import factory

   @factory
   def create_client(config: HttpConfig) -> HttpClient:
       return HttpClient(timeout=config.timeout)

Validation
----------

Call :meth:`~uncoiled.Container.validate` to eagerly detect problems before
starting:

.. code-block:: python

   c = Container()
   c.register(UserService)
   # UserRepository not registered --- validate catches it
   c.validate()  # raises DependencyResolutionError

The error message lists every failure with suggestions:

.. code-block:: text

   Cannot build dependency graph (1 failure):
     1. Missing dependency for UserService.__init__: parameter 'repo'
        requires type 'UserRepository', but no matching component is
        registered.
        Suggestion: Register a component of type UserRepository.
