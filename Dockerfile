FROM python:3.8.2-slim

WORKDIR app

# NOTE(krishan711): Git is only needed whilst py wheel hosted on  github
RUN apt-get update \
    && apt-get install -y --no-install-recommends git
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt $WORKDIR
RUN pip install -r requirements.txt
COPY requirements-dev.txt $WORKDIR
RUN pip install -r requirements-dev.txt

COPY . $WORKDIR
