FROM python:3.11.0-slim as build

RUN apt-get update && apt-get install --yes --no-install-recommends make

# NOTE(krishan711): Git is only needed whilst py wheel hosted on  github
# NOTE(krishan711): GCC (and others) needed to build some dependencies. Remove when everything has a wheel.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git gcc libc-dev \
    && pip install cytoolz==0.11.0 \
    && pip install bitarray==1.2.2 \
    && pip install lru-dict==1.1.7 \
    && pip install httptools==0.1.1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get purge -y --auto-remove git gcc libc-dev

WORKDIR /app
COPY makefile $WORKDIR

COPY requirements-dev.txt $WORKDIR
COPY requirements.txt $WORKDIR
RUN make install

COPY . $WORKDIR
