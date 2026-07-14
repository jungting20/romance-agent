# Frontend TanStack Query Instructions Design

## Goal

Make TanStack Query v5 (`@tanstack/react-query`) the required frontend mechanism for server-state reads and writes, while preserving the repository's existing domain and infrastructure boundaries.

## Instruction placement

Add a dedicated `TanStack Query and API Access` section to `frontend/AGENTS.md` near the existing React and API guidance. The rule applies to frontend agents implementing or changing API-consuming behavior.

## Required behavior

- Implement server-state reads with TanStack Query queries and server-state changes with mutations.
- Keep direct HTTP calls out of React components. Query and mutation functions call typed API adapters responsible for transport and response conversion.
- Configure `QueryClient` and `QueryClientProvider` in `src/app`, not in domain modules or reusable presentation components.
- Define stable, feature-scoped query keys and handle cache invalidation or updates explicitly after successful mutations.
- Represent reachable loading, error, empty, disabled, and success states in consuming UI.
- Keep pure domain code independent of TanStack Query, React, browser APIs, and transport details.
- Test observable query and mutation behavior with Testing Library and MSW, including meaningful success and failure responses.
- Do not introduce an alternative server-state library or bypass TanStack Query for API access without explicit main-agent approval.

## Dependency rule

The instructions name `@tanstack/react-query` v5 explicitly. When API-consuming implementation first requires it, adding that package is considered part of the assigned API task; unrelated dependencies still require main-agent approval.

## Scope

This change updates agent guidance only. It does not install the package or refactor the current API implementation.

## Acceptance criteria

- `frontend/AGENTS.md` explicitly requires `@tanstack/react-query` v5 for frontend server state.
- The guidance specifies architecture boundaries, query-key and cache behavior, UI states, and MSW-backed testing.
- The guidance does not make TanStack Query a dependency of pure domain code.
- Existing API spec ownership and MSW contract requirements remain unchanged.
