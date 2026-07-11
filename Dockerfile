# syntax=docker/dockerfile:1

# --- builder ---
FROM python:3.12-slim AS builder

# Pin uv to the version mise uses for the repo, so image builds match local builds.
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Code
COPY src ./src
RUN uv sync --frozen --no-dev

# --- runtime ---
FROM python:3.12-slim

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid 1000 --create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH"

USER app

# Launch!
CMD ["python", "-m", "feed2epub", "--config", "/config/feeds.yaml"]
