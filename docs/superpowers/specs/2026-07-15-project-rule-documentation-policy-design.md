# Project Rule Documentation Policy Design

## Summary

Add one repository-wide policy to the root `AGENTS.md` that keeps detailed
frontend and backend engineering rules in each application's `docs/`
directory. New coding, architecture, testing, dependency, framework, and
implementation-convention rules discovered while working must update the
appropriate project documentation instead of accumulating in
`frontend/AGENTS.md` or `backend/AGENTS.md`.

The nested `AGENTS.md` files remain concise operational entry points. They may
identify authoritative documents and define agent scope, ownership, workflow,
and verification responsibilities, but they do not become the source of truth
for detailed engineering rules.

## Goals

- Keep detailed frontend rules under `frontend/docs/`.
- Keep detailed backend rules under `backend/docs/`.
- Prevent `frontend/AGENTS.md` and `backend/AGENTS.md` from growing into
  duplicated coding-rule manuals.
- Make implementation and its newly discovered or changed engineering rule one
  synchronized change.
- Preserve a clear distinction between persistent project knowledge and agent
  operating instructions.

## Non-goals

- Move existing nested `AGENTS.md` content as part of this change.
- Change domain-document ownership or synchronization rules.
- Move repository-wide delegation, OpenAPI approval, review, or verification
  authority out of the root `AGENTS.md`.
- Require a new documentation file for every small rule.
- Duplicate this policy into frontend or backend `AGENTS.md`.

## Policy Location

The policy is authored once in the root `AGENTS.md`, near the repository-wide
documentation and domain-boundary rules. It applies to both application trees
without copying the policy into either nested instruction file.

This placement is authoritative because the root instructions apply to the
entire repository and every frontend or backend agent must read them before
working.

## Rule Classification

The following application-specific details belong under the owning
application's `docs/` directory:

- code organization and architecture conventions;
- language and framework usage rules;
- component, package, module, or layering conventions;
- testing, mocking, fixture, and test-placement rules;
- dependency and library usage conventions;
- error handling, state management, persistence, and adapter conventions;
- implementation patterns or constraints discovered while completing work.

Frontend rules go under `frontend/docs/`. Backend rules go under
`backend/docs/`.

The following remain appropriate for `AGENTS.md`:

- agent scope and file ownership;
- task delegation and sequencing;
- required documents to read;
- authority and approval boundaries;
- required verification and handoff behavior;
- repository-wide domain, OpenAPI, review, and working-tree rules.

If a statement mixes operational instructions with a detailed engineering
rule, `AGENTS.md` keeps only the routing or obligation and links to the detailed
rule in the owning project's documentation.

## Document Selection

When adding or changing an application-specific engineering rule:

1. Update the existing authoritative coding-rules document when the topic fits:
   - `frontend/docs/frontend-coding-rules.md` for frontend rules;
   - `backend/docs/backend-coding-rules.md` for backend rules.
2. If the topic is large or distinct enough to need a focused document, create
   it under the same application's `docs/` directory.
3. Link a new focused document from the application's existing coding-rules
   document so readers can discover the complete rule set from one entry point.
4. Do not copy the detailed rule body into `frontend/AGENTS.md` or
   `backend/AGENTS.md`.

This avoids unnecessary one-rule files while allowing mature topics to grow
without making a single coding-rules document unwieldy.

## Synchronization Requirement

When implementation work introduces, changes, or reveals an engineering rule
that should persist, the implementation and the matching project-document
update are one indivisible change. The rule must not be deferred to a later
task and must not be recorded only in an agent handoff or conversation.

This synchronization requirement applies only when the work creates or changes
a reusable rule. Ordinary implementation that follows existing documented
rules does not require a documentation rewrite.

## Relationship to Domain Documentation

This policy does not replace `docs/domains/*.md`. Domain responsibilities,
ubiquitous language, models, invariants, use cases, inputs, outputs, and
dependency directions continue to follow the existing domain-document rules.

An implementation change may therefore require both:

- a project engineering-rule update under `frontend/docs/` or `backend/docs/`;
  and
- a domain-contract update under `docs/domains/`.

Each document records a different kind of truth and both must be synchronized
when both kinds of meaning change.

## Verification

Because this change adds repository policy rather than application behavior,
verification consists of:

- checking that the root `AGENTS.md` contains the frontend and backend docs
  destinations;
- checking that it explicitly prohibits adding detailed engineering rules to
  the nested `AGENTS.md` files;
- checking that it distinguishes detailed project rules from agent operation
  and repository-wide authority;
- checking that it requires same-change synchronization when a reusable rule
  is introduced or changed;
- checking that it instructs authors to link focused documents from the
  existing coding-rules entry point;
- confirming no frontend or backend nested `AGENTS.md`, application source,
  OpenAPI contract, or domain contract changed.

Application checks are not required because no application behavior or build
configuration changes.

## Acceptance Criteria

- The root `AGENTS.md` is the only implementation file changed.
- Detailed frontend engineering rules are directed to `frontend/docs/`.
- Detailed backend engineering rules are directed to `backend/docs/`.
- Existing `frontend/docs/frontend-coding-rules.md` and
  `backend/docs/backend-coding-rules.md` are the default destinations when a
  rule fits their scope.
- A focused project document may be created when warranted and must be linked
  from the existing coding-rules document.
- Detailed rule bodies must not be added to `frontend/AGENTS.md` or
  `backend/AGENTS.md`.
- Nested `AGENTS.md` files remain responsible for agent scope, ownership,
  required reading, authority, workflow, verification, and handoff instructions.
- Repository-wide delegation, OpenAPI, domain, review, and working-tree policy
  remains in the root `AGENTS.md`.
- Implementation and any newly introduced or changed reusable engineering rule
  are documented in the same change.
- Existing domain-document synchronization requirements remain unchanged.
