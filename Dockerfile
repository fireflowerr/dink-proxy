# syntax=docker/dockerfile:1

FROM python:3.14-slim

# uv is copied in as a static binary; it is only used to install at build time,
# the image still runs on the plain virtualenv interpreter.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies from the lock file first, without the project itself, so
# this layer stays cached when only the source changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev --group prod

# Runtime config: host/port settings read by the entry point
COPY config.toml ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --group prod

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 5000

CMD ["python", "-u", "-m", "dinkproxy.main"]
