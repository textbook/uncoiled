from typing import Annotated

import anyio
import httpx
import pytest
from fastapi import Depends, FastAPI, Request

from uncoiled import Container, Scope
from uncoiled.fastapi import (
    Inject,
    RequestScopeMiddleware,
    RequestValueProvider,
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

    @pytest.mark.anyio
    async def test_inject_shorthand_resolves_from_container(self) -> None:
        c = Container()
        c.register(Repository)
        app = FastAPI()
        configure_container(app, c)

        @app.get("/")
        def index(repo: Inject[Repository]) -> dict:
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
        app.add_middleware(RequestScopeMiddleware, container=c)  # ty: ignore[invalid-argument-type]
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
        app.add_middleware(RequestScopeMiddleware, container=c)  # ty: ignore[invalid-argument-type]
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


def _get_ctr(request: Request) -> Container:
    return request.app.state.uncoiled_container


class _TenantId(str):
    __slots__ = ()


class TestRequestValueProvider:
    @pytest.mark.anyio
    async def test_request_value_seeded_from_header(self) -> None:
        class TenantRepo:
            def __init__(self, tenant: _TenantId) -> None:
                self.tenant = tenant

        providers = [
            RequestValueProvider(
                _TenantId,
                lambda r: _TenantId(r.headers["x-tenant-id"]),
            ),
        ]
        c = Container()
        c.register(TenantRepo, scope=Scope.REQUEST)
        app = FastAPI()
        app.add_middleware(
            RequestScopeMiddleware,  # ty: ignore[invalid-argument-type]
            container=c,
            request_values=providers,
        )
        configure_container(app, c, request_values=providers)

        @app.get("/")
        def index(repo: Inject[TenantRepo]) -> dict:
            return {"tenant": repo.tenant}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/",
                headers={"x-tenant-id": "acme"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"tenant": "acme"}

    @pytest.mark.anyio
    async def test_qualified_request_value(self) -> None:
        c = Container()
        app = FastAPI()
        app.add_middleware(
            RequestScopeMiddleware,  # ty: ignore[invalid-argument-type]
            container=c,
            request_values=[
                RequestValueProvider(
                    str,
                    lambda r: r.headers.get(
                        "x-correlation-id",
                        "",
                    ),
                    qualifier="correlation_id",
                ),
            ],
        )
        configure_container(app, c)

        @app.get("/")
        def index(
            ctr: Annotated[Container, Depends(_get_ctr)],
        ) -> dict:
            cid = ctr.get(str, qualifier="correlation_id")
            return {"cid": cid}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                "/",
                headers={"x-correlation-id": "req-42"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"cid": "req-42"}

    @pytest.mark.anyio
    async def test_extractor_error_includes_context(self) -> None:
        providers = [
            RequestValueProvider(
                _TenantId,
                lambda r: _TenantId(r.headers["x-nonexistent"]),
            ),
        ]
        c = Container()
        app = FastAPI()
        app.add_middleware(
            RequestScopeMiddleware,  # ty: ignore[invalid-argument-type]
            container=c,
            request_values=providers,
        )
        configure_container(app, c, request_values=providers)

        @app.get("/")
        def index(
            ctr: Annotated[Container, Depends(_get_ctr)],
        ) -> dict:
            return {"tenant": ctr.get(_TenantId)}

        with pytest.raises(ValueError, match="_TenantId"):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(
                    app=app,
                    raise_app_exceptions=True,
                ),
                base_url="http://test",
            ) as client:
                await client.get("/")

    @pytest.mark.anyio
    async def test_extractor_error_includes_qualifier(self) -> None:
        providers = [
            RequestValueProvider(
                str,
                lambda r: r.headers["x-nonexistent"],
                qualifier="my_qual",
            ),
        ]
        c = Container()
        app = FastAPI()
        app.add_middleware(
            RequestScopeMiddleware,  # ty: ignore[invalid-argument-type]
            container=c,
            request_values=providers,
        )
        configure_container(app, c)

        @app.get("/")
        def index(
            ctr: Annotated[Container, Depends(_get_ctr)],
        ) -> dict:
            return {"val": ctr.get(str, qualifier="my_qual")}

        with pytest.raises(ValueError, match="my_qual"):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(
                    app=app,
                    raise_app_exceptions=True,
                ),
                base_url="http://test",
            ) as client:
                await client.get("/")

    @pytest.mark.anyio
    async def test_concurrent_requests_isolated(self) -> None:
        providers = [
            RequestValueProvider(
                _TenantId,
                lambda r: _TenantId(r.headers["x-tenant-id"]),
            ),
        ]
        c = Container()
        app = FastAPI()
        app.add_middleware(
            RequestScopeMiddleware,  # ty: ignore[invalid-argument-type]
            container=c,
            request_values=providers,
        )
        configure_container(app, c, request_values=providers)

        @app.get("/")
        def index(
            ctr: Annotated[Container, Depends(_get_ctr)],
        ) -> dict:
            return {"tenant": ctr.get(_TenantId)}

        results: list[httpx.Response] = []

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:

            async def _fetch(tenant: str) -> None:
                resp = await client.get(
                    "/",
                    headers={"x-tenant-id": tenant},
                )
                results.append(resp)

            async with anyio.create_task_group() as tg:
                tg.start_soon(_fetch, "acme")
                tg.start_soon(_fetch, "globex")

        tenants = {r.json()["tenant"] for r in results}
        assert tenants == {"acme", "globex"}


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

    @pytest.mark.anyio
    async def test_lifespan_preserves_preconfigured_container(self) -> None:
        """Lifespan must not overwrite a container set by configure_container."""
        test_container = Container()
        test_container.register(Repository)

        prod_container = Container()

        app = FastAPI(lifespan=uncoiled_lifespan(prod_container))
        configure_container(app, test_container)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Trigger a request so the lifespan runs
            await client.get("/nonexistent")

        assert app.state.uncoiled_container is test_container
