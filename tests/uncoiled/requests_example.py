import logging

import requests
import uncoiled

logger = logging.getLogger(__name__)


@uncoiled.register
class LoggedSession(requests.Session):

    def send(
        self,
        request: requests.PreparedRequest,
        **kwargs,
    ) -> requests.Response:
        response = super().send(request)
        logger.info("%s %s: %d", request.method, request.url, response.status_code)
        return response


@uncoiled.inject
class Fetcher:

    def __init__(self, session: requests.Session):
        self._session = session

    def make_request(self, url: str) -> None:
        res = self._session.get(url)
        res.raise_for_status()


if __name__ == "__main__":
    Fetcher().make_request(url="https://example.com")
