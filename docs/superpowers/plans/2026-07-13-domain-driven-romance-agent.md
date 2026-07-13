# Domain-Driven Romance Agent Implementation Plan

> **For agentic workers:** Execute each task test-first and verify each checkpoint before continuing.

**Goal:** Build a navigable, locally persisted romance-writing UI prototype using bounded-context vertical slices.

**Architecture:** Pure TypeScript domain modules expose public APIs. Feature modules orchestrate cross-domain workflows, pages compose feature and module UI, and a localStorage adapter persists a versioned application snapshot.

**Tech Stack:** mise, Node 24.18.0, pnpm 11.4.0, React, TypeScript 7, Vite 8.1, Tailwind CSS v4, shadcn/ui, Oxlint, Oxfmt, Vitest, Testing Library.

## Tasks

1. Configure the pinned toolchain, Vite app, shadcn/ui theme, quality commands, and routing shell.
2. Implement projects, story-design, story-bible, manuscript, and writing-assistant domain behavior test-first.
3. Add versioned persistence and create/open/apply cross-domain use cases test-first.
4. Build the library, trope selection, project setup, and workspace UI.
5. Add assistant interactions and integration tests.
6. Run format, lint, typecheck, tests, build, and browser acceptance checks.
