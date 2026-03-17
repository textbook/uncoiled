FROM mcr.microsoft.com/devcontainers/python:dev-3.14-trixie

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

USER vscode

RUN curl -fsSL https://claude.ai/install.sh | bash

ENTRYPOINT ["top", "-b"]
