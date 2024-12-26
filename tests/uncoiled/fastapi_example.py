from http import HTTPStatus

import uncoiled
import uvicorn
from fastapi import APIRouter, FastAPI


@uncoiled.factory
class HealthController:

    def get_health(self) -> None:
        return None


@uncoiled.factory
def create_app(routers: uncoiled.Every[APIRouter]) -> FastAPI:
    app = FastAPI()
    for router in routers:
        app.include_router(router)
    return app


@uncoiled.factory
def create_health_router(controller: HealthController) -> APIRouter:
    health_router = APIRouter()

    @health_router.get("/healthz", status_code=HTTPStatus.NO_CONTENT)
    def _() -> None:
        return controller.get_health()

    return health_router


@uncoiled.factory
class Server(uvicorn.Server):

    def __init__(self, app: FastAPI) -> None:
        super().__init__(uvicorn.Config(app))


if __name__ == "__main__":
    uncoiled.get(Server).run()
