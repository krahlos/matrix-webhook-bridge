# 1) Build stage — installs the package into an isolated venv
FROM python:3.12-slim AS build

WORKDIR /app

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Install package (no external deps — this mainly resolves the entry point)
COPY pyproject.toml README.md ./
COPY matrix_webhook_bridge/ ./matrix_webhook_bridge/
RUN pip install --no-cache-dir .


# 2) Runtime stage
FROM python:3.12-slim

ARG MAINTAINER="unknown"
ARG VERSION="0.0.0-dev"
ARG IMAGE_REVISION="unknown"
ARG BUILD_DATE="unknown"
ARG SOURCE_URL="https://github.com/krahlos/matrix-webhook-bridge"

LABEL org.opencontainers.image.title="Matrix Webhook Bridge"
LABEL org.opencontainers.image.description="Webhook-to-Matrix notification bridge with per-sender bot users"
LABEL org.opencontainers.image.source="${SOURCE_URL}"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.revision="${IMAGE_REVISION}"
LABEL org.opencontainers.image.created="${BUILD_DATE}"
LABEL org.opencontainers.image.authors="${MAINTAINER}"

RUN apt-get update \
 && apt-get install -y --no-install-recommends wget \
 && rm -rf /var/lib/apt/lists/*

# Dedicated non-root user
RUN addgroup --gid 1001 --system bridge \
 && adduser  --uid 1001 --system --ingroup bridge --no-create-home bridge

COPY --from=build /venv /venv

ENV PATH="/venv/bin:$PATH"
# Flush stdout/stderr immediately so JSON logs reach the container runtime
ENV PYTHONUNBUFFERED=1
ENV PORT=5001

VOLUME ["/tokens"]

USER bridge

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["matrix-webhook-bridge", "healthcheck"]

CMD ["matrix-webhook-bridge", "serve", "--config", "/etc/matrix-webhook-bridge/bridge.yml"]
