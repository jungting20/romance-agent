# Backend

FastAPI application code is organized by domain under `apps/`.

## Setup

From this directory:

```sh
mise install
mise exec -- uv sync --dev
```

## Development server

```sh
mise exec -- uv run uvicorn main:app --reload
```

The process health endpoint is available at `GET /health`.

## Verification

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```
