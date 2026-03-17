import asyncio

from uncoiled import async_call_destroy, async_call_init, call_destroy, call_init


class TestCallInit:
    def test_calls_named_method(self) -> None:
        class Service:
            started = False

            def start(self) -> None:
                self.started = True

        svc = Service()
        call_init(svc, "start")
        assert svc.started

    def test_noop_when_no_method(self) -> None:
        call_init(object())


class TestCallDestroy:
    def test_calls_named_method(self) -> None:
        class Service:
            stopped = False

            def stop(self) -> None:
                self.stopped = True

        svc = Service()
        call_destroy(svc, "stop")
        assert svc.stopped

    def test_calls_close_on_disposable(self) -> None:
        class Resource:
            closed = False

            def close(self) -> None:
                self.closed = True

        res = Resource()
        call_destroy(res)
        assert res.closed

    def test_explicit_method_takes_priority(self) -> None:
        class Resource:
            closed = False
            stopped = False

            def close(self) -> None:
                self.closed = True

            def stop(self) -> None:
                self.stopped = True

        res = Resource()
        call_destroy(res, "stop")
        assert res.stopped
        assert not res.closed

    def test_noop_when_no_method(self) -> None:
        call_destroy(object())


class TestAsyncCallInit:
    def test_calls_async_init(self) -> None:
        class Service:
            started = False

            async def start(self) -> None:
                self.started = True

        svc = Service()
        asyncio.run(async_call_init(svc, "start"))
        assert svc.started

    def test_calls_sync_init(self) -> None:
        class Service:
            started = False

            def start(self) -> None:
                self.started = True

        svc = Service()
        asyncio.run(async_call_init(svc, "start"))
        assert svc.started


class TestAsyncCallDestroy:
    def test_calls_async_aclose(self) -> None:
        class Resource:
            closed = False

            async def aclose(self) -> None:
                self.closed = True

        res = Resource()
        asyncio.run(async_call_destroy(res))
        assert res.closed

    def test_falls_back_to_sync_close(self) -> None:
        class Resource:
            closed = False

            def close(self) -> None:
                self.closed = True

        res = Resource()
        asyncio.run(async_call_destroy(res))
        assert res.closed
