FROM python:3.12.8-slim

ENV PYTHONPATH=${PYTHONPATH}:${PWD}
WORKDIR /opt/app

RUN python -m pip install --upgrade pip && pip install --upgrade pip setuptools
RUN pip install poetry==1.5.1
RUN poetry config virtualenvs.create false

COPY ./pyproject.toml ./poetry.lock /opt/app/
RUN poetry install -n
