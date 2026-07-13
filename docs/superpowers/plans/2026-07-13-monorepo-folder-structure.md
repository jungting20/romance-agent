# Monorepo Folder Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the existing React/Vite application into `frontend/`, reserve `backend/` for a future Python API, and retain shared documentation and toolchain configuration at the repository root.

**Architecture:** The repository root becomes the monorepo boundary. Frontend package ownership moves as a unit without changing imports or runtime behavior; root-level mise configuration remains discoverable from both application directories, and shared documentation stays outside either application.

**Tech Stack:** Git, mise, Node 24.18.0, pnpm 11.4.0, React, Vite, TypeScript 7, future Python backend.

## Global Constraints

- Keep `docs/`, `.gitignore`, `mise.toml`, and `mise.lock` at the repository root.
- Move the complete tracked React/Vite project into `frontend/` without changing application behavior or domain boundaries.
- Create no Python framework or backend application code during this restructure.
- Do not commit generated `node_modules/`, `dist/`, or TypeScript build-info files.

---

### Task 1: Establish Application Directory Boundaries

**Files:**

- Create: `backend/README.md`
- Create: `frontend/`
- Move: `.oxfmtrc.json` to `frontend/.oxfmtrc.json`
- Move: `components.json` to `frontend/components.json`
- Move: `index.html` to `frontend/index.html`
- Move: `package.json` to `frontend/package.json`
- Move: `pnpm-lock.yaml` to `frontend/pnpm-lock.yaml`
- Move: `src/` to `frontend/src/`
- Move: `tsconfig.app.json` to `frontend/tsconfig.app.json`
- Move: `tsconfig.json` to `frontend/tsconfig.json`
- Move: `tsconfig.node.json` to `frontend/tsconfig.node.json`
- Move: `vite.config.ts` to `frontend/vite.config.ts`
- Modify: `.gitignore`

**Interfaces:**

- Consumes: the existing frontend package and root mise toolchain.
- Produces: independently owned `frontend/` and `backend/` application boundaries.

- [ ] **Step 1: Capture the clean frontend baseline**

Run from the repository root:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: 35 tests pass and the Vite production build exits successfully.

- [ ] **Step 2: Move tracked frontend files with Git history**

Create `frontend/`, then use `git mv` for every tracked frontend path listed in this task. Leave `docs/`, `.gitignore`, `mise.toml`, and `mise.lock` at the root.

Expected: `git status --short` reports renames into `frontend/` rather than deleted-and-recreated application files.

- [ ] **Step 3: Create the backend boundary marker**

Create `backend/README.md` with this content:

```markdown
# Backend

Python API application code will live in this directory. The framework and package layout will be selected when backend implementation begins.
```

- [ ] **Step 4: Extend repository-wide generated-file ignores**

Keep the existing frontend patterns and add Python generated files to `.gitignore`:

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 5: Remove stale root-only generated artifacts**

Remove the ignored root `node_modules/`, `dist/`, `tsconfig.app.tsbuildinfo`, and `tsconfig.node.tsbuildinfo`. These are regenerated under `frontend/` by installation, type checking, and building.

- [ ] **Step 6: Verify the directory boundary**

Run:

```sh
git status --short
git check-ignore frontend/node_modules frontend/dist frontend/tsconfig.app.tsbuildinfo
```

Expected: application paths appear under `frontend/`; each generated frontend path is ignored by the root `.gitignore`.

### Task 2: Restore and Verify the Frontend from Its New Root

**Files:**

- Verify: `frontend/package.json`
- Verify: `frontend/pnpm-lock.yaml`
- Verify: `frontend/src/`
- Verify: `mise.toml`
- Verify: `mise.lock`

**Interfaces:**

- Consumes: the `frontend/` package boundary produced by Task 1.
- Produces: a reproducible frontend package that passes the same quality and build gates from its new directory.

- [ ] **Step 1: Install the locked frontend dependencies**

Run from `frontend/`:

```sh
mise exec -- pnpm install --frozen-lockfile
```

Expected: pnpm restores dependencies without changing `pnpm-lock.yaml`.

- [ ] **Step 2: Run the complete frontend quality gate**

Run from `frontend/`:

```sh
mise exec -- pnpm check
```

Expected: formatting, Oxlint, TypeScript, and all 35 tests pass.

- [ ] **Step 3: Build the frontend production bundle**

Run from `frontend/`:

```sh
mise exec -- pnpm build
```

Expected: Vite builds the production bundle under `frontend/dist/` successfully.

- [ ] **Step 4: Inspect the final repository shape**

Run from the repository root:

```sh
git status --short
git diff --check
git ls-files backend frontend docs
```

Expected: only the intended structure changes are present, generated files are absent from the tracked-file list, and whitespace validation passes.

- [ ] **Step 5: Commit the restructure**

```sh
git add .gitignore backend frontend
git commit -m "refactor: split frontend and backend directories"
```
