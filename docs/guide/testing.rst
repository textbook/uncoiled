Testing
=======

Uncoiled provides several mechanisms for testing with dependency injection.

Override Context Manager
------------------------

:meth:`~uncoiled.Container.override` temporarily replaces a registration:

.. code-block:: python

   mock_repo = MockUserRepository()
   with container.override(UserRepository, mock_repo):
       service = container.get(UserService)
       assert isinstance(service.repo, MockUserRepository)
   # original registration restored

Fork
----

:meth:`~uncoiled.Container.fork` creates a child container that inherits all
registrations but can override them independently:

.. code-block:: python

   child = container.fork()
   child.register(MockMailer, provides=Mailer, replace=True)
   # parent container is unaffected

Pytest Plugin
-------------

The built-in pytest plugin (auto-discovered via entry point) provides:

**Fixtures:**

- ``uncoiled_container`` (session-scoped) --- a started container
- ``inject`` (function-scoped) --- a :class:`~uncoiled.Resolve` helper

**Usage:**

.. code-block:: python

   def test_user_service(inject):
       service = inject[UserService]
       assert isinstance(service.repo, UserRepository)

**Override marker:**

.. code-block:: python

   import pytest
   from uncoiled import Resolve

   @pytest.mark.uncoiled_override(UserRepository, MockRepository)
   def test_with_mock(inject: Resolve):
       service = inject[UserService]
       assert isinstance(service.repo, MockRepository)

The marker accepts an optional ``qualifier`` keyword argument.

Setup
^^^^^

To use the plugin, define a ``uncoiled_container`` fixture in your
``conftest.py`` that builds and yields your container:

.. code-block:: python

   import pytest
   from uncoiled import Container

   @pytest.fixture(scope="session")
   def uncoiled_container():
       c = Container()
       c.scan("myapp")
       with c:
           yield c

Unit Tests Without the Framework
---------------------------------

Because components use plain constructor injection, unit tests can
instantiate classes directly without any DI framework:

.. code-block:: python

   def test_user_service():
       repo = MockUserRepository()
       service = UserService(repo)
       assert service.create_user("Alice").name == "Alice"
