# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
#
# CRP HTTP Sidecar — lightweight container for inter-process context sharing.
#
# Build:
#   docker build -t crp-sidecar .
#
# Run (basic, loopback only inside container):
#   docker run -p 8900:8900 crp-sidecar
#
# Run (with auth token for production):
#   docker run -p 8900:8900 \
#     -e CRP_AUTH_TOKEN=your-secret-token \
#     -e OPENAI_API_KEY=sk-... \
#     crp-sidecar
#
# Run with persistent session storage:
#   docker run -p 8900:8900 \
#     -v crp-sessions:/app/crp_sessions \
#     -e CRP_AUTH_TOKEN=your-secret-token \
#     crp-sidecar

FROM python:3.13-slim AS base

LABEL maintainer="AutoCyber AI <contact@autocyberai.com>"
LABEL description="CRP HTTP Sidecar — Context Relay Protocol inter-process API"
LABEL org.opencontainers.image.source="https://github.com/Constantinos-uni/context-relay-protocol"
LABEL org.opencontainers.image.licenses="LicenseRef-ELv2"

# Security: run as non-root
RUN groupadd -r crp && useradd -r -g crp -d /app -s /sbin/nologin crp

WORKDIR /app

# Install only what's needed (no dev dependencies)
COPY pyproject.toml README.md LICENSE.md ./
COPY crp/ ./crp/

RUN pip install --no-cache-dir -e ".[cli]" && \
    pip install --no-cache-dir -e ".[security]"

# Session data volume
RUN mkdir -p /app/crp_sessions && chown crp:crp /app/crp_sessions
VOLUME ["/app/crp_sessions"]

# Switch to non-root user
USER crp

# Default port
EXPOSE 8900

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8900/health')" || exit 1

# Entry point: serve with bind-all (container networking requires 0.0.0.0)
# Auth token is required when binding to all interfaces.
# Shell form is required for $CRP_AUTH_TOKEN expansion.
ENTRYPOINT ["crp", "serve", "--bind-all", "--port", "8900"]

# Default: require auth token via environment variable
# Override with: docker run ... crp-sidecar --allow-unauthenticated
# NOTE: must use shell form so $CRP_AUTH_TOKEN is expanded at runtime
CMD ["sh", "-c", "exec crp serve --bind-all --port 8900 --auth-token \"$CRP_AUTH_TOKEN\""]
