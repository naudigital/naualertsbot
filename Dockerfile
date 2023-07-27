FROM python:3.11-slim-buster as build
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100
WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install --no-install-recommends -y curl && \
    rm -rf /var/lib/apt/lists/*

RUN sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b /usr/bin

RUN pip install -U pip poetry && \
    poetry config virtualenvs.create false

COPY . /usr/src/app/

RUN task build

FROM python:3.11-slim-buster as runtime
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100
WORKDIR /app

RUN mkdir -p /opt/app
COPY --from=build /usr/src/app/dist/naualertsbot-*.whl /opt/app
RUN pip install /opt/app/naualertsbot-*.whl && \
    rm -rf /opt/app

COPY assets /app/assets

CMD [ "naualertsbot" ]
