# API image. The build context is the repository root (infra/lib/service.ts), so
# BuildKit reads Dockerfile.dockerignore beside this file.
FROM ghcr.io/astral-sh/uv:0.11.8 AS uv

# ponytail: the ECR Public mirror of the Docker official image avoids the Docker Hub
# pull limit; switch back to docker.io/library/python if the mirror lags.
FROM public.ecr.aws/docker/library/python:3.13.18-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/api/.venv/bin:$PATH"

WORKDIR /app/api
COPY --from=uv /uv /usr/local/bin/uv
COPY api/pyproject.toml api/uv.lock api/.python-version ./
# No dev group and no agent group: the guide waits (D-11 b).
RUN uv sync --frozen --no-dev

COPY api/boramae ./boramae
COPY content /app/content

# uvicorn's own logging, plus the boramae loggers at INFO (no code sets a level).
COPY <<'EOF' /app/api/log-config.json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "default": {
      "()": "uvicorn.logging.DefaultFormatter",
      "fmt": "%(levelprefix)s %(name)s %(message)s",
      "use_colors": false
    }
  },
  "handlers": {
    "default": {
      "class": "logging.StreamHandler",
      "formatter": "default",
      "stream": "ext://sys.stderr"
    }
  },
  "loggers": {
    "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": false},
    "uvicorn.error": {"level": "INFO"},
    "boramae": {"handlers": ["default"], "level": "INFO", "propagate": false}
  }
}
EOF

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin boramae
USER 10001
EXPOSE 8000

# --no-access-log: the access log prints the client address and the query string.
CMD ["uvicorn", "boramae.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--no-access-log", "--log-config", "/app/api/log-config.json"]
