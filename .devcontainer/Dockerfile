FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04 AS opc-toolchain

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        clang \
        clangd \
        cmake \
        curl \
        dnsutils \
        gdb \
        git \
        iproute2 \
        iputils-ping \
        jq \
        less \
        libssl-dev \
        lldb \
        lsof \
        nano \
        netcat-openbsd \
        ninja-build \
        nodejs \
        npm \
        openssl \
        pkg-config \
        procps \
        psmisc \
        python-is-python3 \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        ripgrep \
        shellcheck \
        socat \
        strace \
        sudo \
        tcpdump \
        tini \
        unzip \
        vim \
        wget \
        zip \
    && rm -rf /var/lib/apt/lists/*

RUN corepack enable || true

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt /tmp/requirements.txt

RUN python3 -m venv /opt/commdev-venv \
    && /opt/commdev-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY scripts /workspace/scripts
COPY apps /workspace/apps

ENV PATH="/opt/commdev-venv/bin:${PATH}"

WORKDIR /workspaces/CommDev

FROM opc-toolchain AS devcontainer

CMD ["sleep", "infinity"]