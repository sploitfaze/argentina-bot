FROM python:3.12-alpine

WORKDIR /application

RUN pip install pipenv

COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --ignore-pipfile --system

COPY . .
