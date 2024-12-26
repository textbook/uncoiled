from __future__ import annotations

import logging
import typing as tp
from http import HTTPStatus

from fastapi.exceptions import HTTPException
from socket import socket
from threading import Thread

import httpx
import pytest
from requests.exceptions import HTTPError

from tests.uncoiled.fastapi_example import HealthController, Server
from tests.uncoiled.requests_example import Fetcher
from uncoiled import overload


class FakeController(HealthController):

    def get_health(self) -> None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND)


@pytest.mark.anyio
async def test_fastapi_example(test_client: httpx.AsyncClient) -> None:
    res = await test_client.get("/healthz")
    assert res.status_code == HTTPStatus.NOT_FOUND


def test_requests_example(
    caplog: pytest.LogCaptureFixture,
    test_server: SocketServer,
) -> None:
    with caplog.at_level(logging.INFO), pytest.raises(HTTPError):
        Fetcher().make_request(url=f"{test_server.url}/healthz")
    logs = caplog.get_records(when="call")
    assert len(logs) == 1
    assert logs[0].getMessage() == f"GET {test_server.url}/healthz: 404"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def test_client(test_server: SocketServer) -> tp.Iterator[httpx.AsyncClient]:
    yield httpx.AsyncClient(base_url=test_server.url)


@pytest.fixture
def test_server() -> tp.Iterator[SocketServer]:
    with SocketServer.random_port() as server:
        yield server


class SocketServer:

    @classmethod
    def random_port(cls) -> SocketServer:
        socket_ = socket()
        socket_.bind(("", 0))
        return cls(socket_)

    def __init__(self, socket_: socket):
        self._server = overload(
            HealthController,
            with_factory=FakeController,
        ).get(Server)
        self._socket = socket_
        self._thread = Thread(
            target=self._server.run,
            kwargs=dict(sockets=[self._socket]),
        )

    def __enter__(self) -> "SocketServer":
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._server.should_exit = True
        self._thread.join()

    @property
    def url(self) -> str:
        host, port = self._socket.getsockname()
        return f"http://{host}:{port}"
