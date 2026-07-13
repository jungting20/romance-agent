# MSW Mock Infrastructure Design

## Goal

Establish Mock Service Worker (MSW) as the frontend's required API-mocking
boundary before adding instructions that require contract-aligned mocks for API
spec work.

## Scope

- Add `msw` as a frontend development dependency.
- Generate and retain the MSW browser worker under `frontend/public/`.
- Add shared request handlers plus browser and Vitest adapters under
  `frontend/src/mocks/`.
- Start browser mocking before React renders in the development environment.
- Start, reset, and stop the MSW server through the existing Vitest setup.
- Update `frontend/AGENTS.md` so every API-spec addition or change must include
  corresponding MSW handlers and mock response data.

There is no API contract yet, so this change will not invent endpoints or
domain payloads. The initial handler collection will be empty and ready for the
first approved API operation.

## Structure and Runtime Behavior

The shared `handlers.ts` module will be the single handler collection used by
both runtimes. `browser.ts` will create the browser worker, and `server.ts` will
create the Node server used by Vitest. A small browser bootstrap module will
dynamically load and start MSW only in the development environment. The
application entry point will await that bootstrap before rendering React so an
initial request cannot escape before interception is active.

Vitest's existing setup module will start the MSW server before the test suite,
reset runtime handler overrides after each test, and close the server after the
suite. Unhandled API requests in tests will fail loudly so tests do not
silently depend on a real service.

## Instruction Contract

`frontend/AGENTS.md` will state that an API-spec task is incomplete until every
affected operation has MSW handlers and representative mock response data.
Mocks must cover the success response and the meaningful contract-declared
error responses exercised by the UI, and their payloads must remain aligned
with the proposed or approved OpenAPI baseline. OpenAPI examples alone do not
satisfy this requirement. The frontend-to-main handoff must identify the MSW
artifacts and report validation results.

## Verification

The implementation will run the frontend's full required checks:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

Focused tests will also verify the MSW server lifecycle and request
interception without adding a fictional product API.
