FROM python:3.12.0-slim

RUN apt-get update && apt-get install --yes --no-install-recommends make git

WORKDIR /app
COPY makefile .

COPY pyproject.toml .
COPY uv.lock .
RUN make install

COPY . .
RUN make type-check
