# Monorepo Folder Structure Design

## Goal

Restructure the repository so the existing React application is clearly owned by `frontend/`, future Python API code is owned by `backend/`, and shared product and architecture documents remain in `docs/`.

## Target Structure

```text
romance-agent/
├── backend/
├── frontend/
├── docs/
├── .gitignore
├── mise.toml
└── mise.lock
```

## Ownership

- `frontend/` contains the complete existing React/Vite project: application source, package manifest and lockfile, Vite and TypeScript configuration, shadcn configuration, formatter configuration, HTML entry point, and generated frontend build artifacts when present locally.
- `backend/` is reserved for the Python API. This restructuring does not select a Python framework or create backend application code. A tracked placeholder documents the directory's purpose.
- `docs/` remains at the repository root because its product, architecture, and implementation documents cover the whole system rather than only the frontend.
- `.gitignore`, `mise.toml`, and `mise.lock` remain at the root. Mise will manage the shared Node, pnpm, and future Python toolchain for the entire repository.

## Command Model

Frontend package commands run from `frontend/`, for example:

```sh
cd frontend
mise exec -- pnpm check
mise exec -- pnpm build
```

Mise discovers the root configuration from the frontend subdirectory. Future backend commands will use the same root toolchain configuration.

## Migration Rules

1. Preserve Git history by moving tracked frontend files rather than recreating them.
2. Do not move `docs/`, `.git/`, `.gitignore`, `mise.toml`, or `mise.lock` into the frontend.
3. Do not move ignored generated directories such as `node_modules/` or `dist/`; remove or regenerate them under `frontend/` as needed.
4. Update root ignore patterns so generated files are ignored regardless of whether they occur under `frontend/` or `backend/`.
5. Do not change application behavior or domain boundaries during the restructure.

## Verification

- The root contains `backend/`, `frontend/`, and `docs/`.
- Frontend formatting, linting, type checking, and all tests pass from `frontend/`.
- The production frontend build succeeds from `frontend/`.
- Git reports moves cleanly and contains no generated dependency or build directories.
