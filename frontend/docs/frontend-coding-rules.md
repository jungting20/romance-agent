# Frontend Coding Rules

## Purpose and Scope

These rules apply when writing or refactoring code under `frontend/`. They
supplement `AGENTS.md`; they do not replace its architecture, domain-contract,
API-approval, accessibility, testing, or verification requirements. If the two
documents appear to conflict, follow `AGENTS.md` and raise the conflict before
editing.

## Page Composition and Workflow Ownership

- Pages coordinate data-loading states and compose modules and features. They
  must not directly implement domain workflows or detailed presentation
  behavior.
- When one user action coordinates multiple domains, feature state,
  persistence, or UI selection state, move that workflow into a feature-level
  application hook or handler. Pages should pass a concise callback to the
  relevant UI component.
- Keep data flow explicit when extracting logic. Prefer typed inputs, outputs,
  and callbacks over child components that independently acquire hidden
  application state.

## State and Hook Interfaces

- Group closely related hook results into cohesive, named interfaces when a
  consumer would otherwise destructure many fields. Examples include `draft`,
  `save`, `conflict`, and `navigation`.
- Grouping a hook interface must not hide state ownership. Do not move an
  application hook into a presentation component merely to shorten its parent.
- Keep state in the nearest common owner that coordinates its consumers, and
  pass only the state slice and callbacks each child requires.
- Extract browser synchronization, navigation guards, subscriptions, and other
  lifecycle behavior into focused hooks when they are independent of page
  rendering.
- Prefer values derived during rendering over additional state or effects.

## Component Extraction and Colocation

- Extract a component when it has an independent responsibility, a meaningful
  interface, or behavior that can be understood and tested in isolation.
- Keep page-specific components colocated with their page or feature. Do not
  promote product-specific components into `src/components/ui` unless they are
  genuinely reusable presentation primitives.
- Prefer a small number of cohesive components over splitting every JSX block,
  constant, or helper into its own file.
- Headers, navigation regions, status displays, dialogs, and conditional panels
  are extraction candidates when they have distinct inputs or behavior.
- Repeated loading, empty, not-found, and error layouts may share a
  presentation shell, but each state must retain the correct semantic role,
  accessible name, actions, and copy.

## Constants, Helpers, and Defensive Checks

- Keep small page-specific constants and pure helpers near their only consumer.
  Extract them when they are reused, independently tested, or represent a
  distinct responsibility.
- Do not add optional chaining, fallback values, or null checks to values that
  domain types and invariants guarantee. Defensive checks must reflect an
  actual boundary or reachable state rather than hide an inaccurate type
  model.
- When a supposedly required value can be absent at runtime, correct the
  authoritative type, validation boundary, or domain invariant before adding
  scattered fallbacks.

## Refactoring and Verification

- Prefer incremental extraction over rewriting an entire page. Preserve
  observable behavior and keep focused tests passing after each extraction.
- Define refactoring success by clearer responsibilities, narrower interfaces,
  and preserved behavior, not by a target file length.
- Before extracting code, identify the current owner of state, domain behavior,
  browser synchronization, and presentation. Preserve or deliberately improve
  those ownership boundaries.
- When a large page test covers independent responsibilities, split it by
  user-visible flow after the implementation boundaries are stable.
- A responsibility-preserving refactor does not require a domain-document
  update. If domain behavior, ownership, invariants, or cross-domain workflows
  change, update the matching domain contract in the same change.
