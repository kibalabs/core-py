FROM python:3.8.2-slim

WORKDIR app

COPY requirements.txt $WORKDIR
RUN pip install -r requirements.txt

COPY . $WORKDIR
