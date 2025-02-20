FROM python:3.11.0-slim

RUN apt-get update && apt-get install --yes --no-install-recommends make

WORKDIR /app
COPY makefile .

COPY pyproject.toml .
COPY uv.lock .
RUN make install

COPY . .
