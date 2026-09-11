# syntax=docker/dockerfile:1

FROM python:3.14-slim

WORKDIR /app

# Install the package, its dependencies, and the production WSGI server.
COPY pyproject.toml ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip pip install ".[prod]"

# Runtime config: host/port settings read by the entry point
COPY config.toml ./
COPY server.py .

EXPOSE 5000

CMD ["python", "-u", "-m", "dinkproxy.main"]
