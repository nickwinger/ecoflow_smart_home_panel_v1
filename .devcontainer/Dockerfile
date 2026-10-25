# Isolated editor/test environment. It is NOT Home Assistant and has no
# access to the production instance or a Docker socket.
FROM python:3.14-slim-bookworm

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl git openssh-client procps build-essential libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" -m -s /bin/bash "${USERNAME}"

COPY requirements-test.txt /tmp/requirements-test.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-test.txt

USER ${USERNAME}
WORKDIR /workspaces/ecoflow_smart_home_panel_v1
