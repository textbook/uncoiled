from typing import Annotated

import httpx
import pytest
from fastapi import FastAPI

from uncoiled import Container, Scope
from uncoiled.fastapi import (
    RequestScopeMiddleware,
    configure_container,
    inject_dependency,
    uncoiled_lifespan,
)


class Repository:
    pass


class UserService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


class TestInjectDependency:
    @pytest.mark.anyio
    async def test_resolves_from_container(self) -> None:
        c = Container()
        c.register(Repository)
        app = FastAPI()
        configure_container(app, c)

        @app.get("/")
        def index(
            repo: Annotated[Repository, inject_dependency(Repository)],
        ) -> dict:
            return {"type": type(repo).__name__}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/")

        assert resp.status_code == 200
        assert resp.json() == {"type": "Repository"}


class TestRequestScopeMiddleware:
    @pytest.mark.anyio
    async def test_request_scope_same_within_request(self) -> None:
        c = Container()
        c.register(Repository, scope=Scope.REQUEST)
        app = FastAPI()
        app.add_middleware(RequestScopeMiddleware, container=c)  # type: ignore[arg-type]
        configure_container(app, c)

        @app.get("/")
        def index(
            r1: Annotated[Repository, inject_dependency(Repository)],
            r2: Annotated[Repository, inject_dependency(Repository)],
        ) -> dict:
            return {"same": r1 is r2}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/")

        assert resp.json()["same"] is True

    @pytest.mark.anyio
    async def test_request_scope_different_across_requests(self) -> None:
        c = Container()
        c.register(Repository, scope=Scope.REQUEST)
        app = FastAPI()
        app.add_middleware(RequestScopeMiddleware, container=c)  # type: ignore[arg-type]
        configure_container(app, c)

        ids: list[int] = []

        @app.get("/")
        def index(
            repo: Annotated[Repository, inject_dependency(Repository)],
        ) -> dict:
            ids.append(id(repo))
            return {}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/")
            await client.get("/")

        assert len(ids) == 2
        assert ids[0] != ids[1]


class TestUncoiledLifespan:
    def test_lifespan_returns_context_manager_factory(self) -> None:
        c = Container()
        lifespan = uncoiled_lifespan(c)
        assert callable(lifespan)

    @pytest.mark.anyio
    async def test_lifespan_starts_and_closes_container(self) -> None:
        class Resource:
            closed = False

            def close(self) -> None:
                self.closed = True

        c = Container()
        c.register(Resource)
        app = FastAPI()
        lifespan = uncoiled_lifespan(c)

        async with lifespan(app):
            # Container should be started and attached to app state
            assert hasattr(app.state, "uncoiled_container")
            assert app.state.uncoiled_container is c
            res = c.get(Resource)
            assert res is not None

        # After exiting, lifespan closes the container
        assert res.closed
