FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Core packages
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    make \
    vim \
    bat \
    fish \
    sudo \
    jq \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Go (latest stable from official tarball)
ARG GO_VERSION=1.23.6
RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-$(dpkg --print-architecture).tar.gz" \
    | tar -C /usr/local -xz
ENV PATH="/usr/local/go/bin:${PATH}"

# Node.js (LTS via NodeSource)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with sudo access
ARG USERNAME=ralph
RUN useradd -m -s /usr/bin/fish ${USERNAME} \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Copy homefiles into image (installed into home by setup.sh at first run)
COPY --chown=${USERNAME}:${USERNAME} homefiles/ /opt/homefiles/

COPY --chmod=755 setup.sh /usr/local/bin/setup.sh
COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

# Run entrypoint as root so it can adjust UID/GID, then exec as ralph
ENTRYPOINT ["entrypoint.sh"]
CMD ["fish"]
