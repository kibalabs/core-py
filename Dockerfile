FROM python:3.14.10-slim

RUN apt-get update && apt-get install --yes --no-install-recommends make git

WORKDIR /app
COPY makefile .

COPY pyproject.toml .
COPY uv.lock .
RUN make install

COPY . .
# NOTE(krishan711): make install ran before core/ was copied in, so reinstall the package itself to make it importable
RUN uv sync --all-extras --reinstall-package kiba-core
