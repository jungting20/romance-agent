# Romance Writing Agent Design

## Product direction

Build a desktop-first, interactive UI prototype for aspiring romance writers. The core journey is library → trope selection → project setup → writing workspace. The prototype uses deterministic assistant responses and browser persistence; real LLM calls, authentication, backend services, cloud sync, and mobile-specific UX are out of scope.

## Experience

- The workspace is manuscript-first, with a domain rail and contextual navigation on the left, a paper-like editor in the center, and a collapsible writing-tools panel on the right.
- The visual language uses cream backgrounds, paper surfaces, ink text, serif headings, and restrained terracotta accents.
- The assistant acts only when requested. It supports continue, refine, dialogue, and consistency actions, with explicit apply or cancel controls.
- New projects begin from a romance trope template and request only a title, logline, and two protagonist names.

## Architecture

Use a modular monolith organized by bounded context. Each module contains pure domain logic, application services, infrastructure adapters, and domain-owned UI. Cross-domain workflows live in features; pages only compose modules and features. Domain code must not import React, browser APIs, or another layer.

Bounded contexts are projects, story design, story bible, manuscript, and writing assistant. The create-project and apply-writing-suggestion features orchestrate those contexts without letting the assistant mutate the manuscript directly.

## Technology

Use mise-pinned Node 24.18.0 and pnpm 11.4.0, TypeScript 7, Vite 8.1, React, React Router, Tailwind CSS v4, and shadcn/ui. Use Oxlint with tsgolint for type-aware linting, Oxfmt for formatting, and Vitest with Testing Library for automated checks.

