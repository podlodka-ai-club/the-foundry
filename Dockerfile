# syntax=docker/dockerfile:1.7

FROM node:24-bookworm-slim AS node_runtime

FROM ghcr.io/astral-sh/uv:python3.12-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/foundry-venv \
    PATH="/opt/foundry-venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gh \
        git \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node_runtime /usr/local/bin /usr/local/bin
COPY --from=node_runtime /usr/local/lib/node_modules /usr/local/lib/node_modules

ARG INSTALL_CLAUDE_CLI=false
ARG INSTALL_CODEX_CLI=false
ARG INSTALL_OPENCODE_CLI=false

RUN if [ "${INSTALL_CLAUDE_CLI}" = "true" ]; then npm install -g @anthropic-ai/claude-code; fi \
    && if [ "${INSTALL_CODEX_CLI}" = "true" ]; then npm install -g @openai/codex; fi \
    && if [ "${INSTALL_OPENCODE_CLI}" = "true" ]; then npm install -g opencode-ai; fi

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY docker/entrypoint.sh /usr/local/bin/foundry-entrypoint

RUN chmod +x /usr/local/bin/foundry-entrypoint

RUN uv sync --frozen --no-dev \
    && mkdir -p /app/data /app/worktrees

EXPOSE 8000

ENTRYPOINT ["foundry-entrypoint"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
