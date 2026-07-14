# Backend Agent Instructions

## Scope

These instructions apply to `backend/` and extend the repository root `AGENTS.md`.

## Architecture

- Put domain code under `apps/{domain}/{router,service,repository,schemas}`.
- Keep HTTP and Pydantic concerns in `router` and `schemas`.
- Keep services independent of FastAPI, browser concerns, persistence technology, and external providers.
- Routers call services; routers must not access repositories directly.
- Cross-domain workflows belong in an application use-case layer introduced when required.

## Verification

Run from `backend/` before completion:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```
