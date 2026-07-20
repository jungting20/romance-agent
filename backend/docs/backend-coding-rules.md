# Backend Coding Rules

## Purpose and Scope

These are the authoritative implementation rules for code under `backend/`.
`AGENTS.md` owns agent scope, approval boundaries, OpenAPI authority, required
verification, and handoff workflows. If the documents conflict, follow
`AGENTS.md` and raise the conflict before editing.

## Architecture and Request Handling

- Put backend code under
  `apps/<domain>/{domain,router,service,repository,schemas}`, omitting a package
  only when that responsibility is not needed.
- Routers translate HTTP input into typed application inputs, invoke a service
  or application use case, and translate its result into the approved response.
  Keep HTTP and Pydantic concerns in `router` and `schemas`.
- Routers call services; they must not implement domain rules or access
  repositories directly.
- Services and application use cases coordinate domain operations and ports.
  When one request spans multiple domains or infrastructure boundaries, keep
  that workflow in an explicit application use case rather than hiding it in a
  router, repository, schema, or provider adapter.
- Keep services and domain behavior independent of FastAPI, Pydantic, browser
  concerns, persistence technology, process globals, and external providers.
- Cross-domain workflows belong in an application use-case layer introduced
  when required.
- Keep request and response shapes, validation ownership, status codes, and
  error semantics aligned with the main-agent-approved OpenAPI baseline.

## Domain Model Ownership

- Put behavior-bearing entities, aggregate roots, value objects, and domain
  errors under `apps/<domain>/domain/`.
- An entity owns invariants and state transitions local to its identity. An
  aggregate root owns invariants and atomic state transitions spanning the
  state inside its aggregate boundary.
- Application services load aggregates, coordinate explicit external
  dependencies, invoke domain behavior, and persist the resulting aggregate.
  They must not reconstruct aggregate-owned state or duplicate
  aggregate-owned business rules.
- Keep transport commands, persistence representations, and domain models as
  separate concepts. Translate between them at the router, application, and
  repository boundaries that own those conversions.
- Do not introduce an entity or aggregate solely to satisfy a package
  structure. Use one when identity, lifecycle, invariant, or state-transition
  ownership gives the model meaningful behavior.

## Dependencies and Interfaces

- Make dependencies explicit through typed parameters, constructors, or ports.
  Do not let domain or service code acquire repositories, clients, settings, or
  process state through hidden globals.
- Define a port when application or domain behavior depends on persistence,
  time, identifier generation, messaging, or an external provider. Keep the
  port focused on the consumer's needs rather than mirroring a vendor API.
- Group closely related inputs and results into cohesive, named types when a
  caller would otherwise pass or unpack many related values. Do not group
  unrelated values merely to shorten a signature.
- Keep transaction and state ownership explicit. A lower layer must not commit,
  mutate, or coordinate state owned by another domain unless its contract
  assigns that responsibility.
- Return domain or application results from services. Convert them to transport
  schemas and HTTP errors at the router boundary.

## Module and Unit Extraction

- Extract a function, class, or module when it has an independent
  responsibility, a meaningful interface, or behavior that can be tested in
  isolation.
- Keep domain-specific code within its owning `apps/<domain>/` package. Move
  code to shared infrastructure only when it is genuinely cross-cutting and
  contains no domain policy.
- Prefer a small number of cohesive modules over splitting every schema,
  helper, constant, or single function into a separate file.
- Keep small domain-specific constants and pure helpers near their only
  consumer. Extract them when they are reused, independently tested, or
  represent a distinct responsibility.
- Do not introduce a generic base repository, service, schema, or exception
  hierarchy before multiple concrete consumers demonstrate the same stable
  abstraction.

## Validation and Defensive Handling

- Validate transport syntax and shape in schemas or routers. Enforce
  entity-local invariants in the owning entity and aggregate-wide invariants in
  the aggregate root. Application services may enforce workflow preconditions
  that span aggregates or external ports and do not belong to one domain model.
- Do not duplicate a business rule across schemas, services, and repositories.
  Make its authoritative owner explicit and translate failures at boundaries.
- Do not add `None` handling, fallback values, broad exception catches, or
  unchecked casts to values that types and invariants guarantee. Defensive
  handling must correspond to a reachable boundary or documented failure.
- When a supposedly required value can be absent at runtime, correct the
  authoritative type, validation boundary, or domain invariant before adding
  scattered fallbacks.
- Catch exceptions only where the code can add context, translate them into a
  defined application or transport error, or perform required cleanup. Do not
  silently swallow failures.

## Durable File Replacement

- For mutable project files, serialize to an owned temporary file in the same
  directory as the canonical file, flush it, call `fsync`, and publish it with
  an atomic `os.replace` only after serialization succeeds.
- Protect compare-and-replace workflows with a project-local sibling lock and
  re-read the canonical file while holding that lock before checking the exact
  expected revision. Lower and higher revision mismatches are both conflicts.
- On failure, remove only the temporary file created by the current operation;
  never truncate, delete, or partially rewrite the canonical file as cleanup.
- Resolve file paths beneath the configured data root and reject identifiers
  containing traversal or absolute-path components before any file access.

## LLM Agent Audit

- Keep provider clients behind narrow typed application ports. Select the model
  only at an explicit composition boundary; domain services must not read model
  settings, provider SDKs, or process globals.
- Store editable, versioned prompt files under `backend/prompts/`. Load the
  prompt for each explicitly requested run so edits are hot-loaded, and require
  a version increment whenever registered prompt bytes change.
- Persist the prompt definition, run start, and attempt start before making a
  provider call. Treat an audit-start failure as call-blocking, and never write
  prompts, manuscript text, model responses, or validated extraction content to
  ordinary console logs.
- Enforce at most one terminal attempt event (`attempt_succeeded` or
  `attempt_failed`) for each run, chunk, and attempt number in both the audit
  port contract and durable storage. A best-effort failure fallback after an
  ambiguous success append may run, but storage must reject it when success was
  already committed; never repair terminal conflicts with update or delete.
  Compare the identity tuple with exact, case-sensitive (`BINARY`) semantics,
  and validate an existing reserved index from SQLite index metadata, including
  key order, collation, sort direction, uniqueness, and partial predicate,
  before accepting it as the durable constraint.
- Validate structured provider output before translating it into domain types.
  Provider adapters must not assign durable domain IDs, candidate states, or
  other domain-owned meaning.
- Supply scripted, network-free adapters for service and integration tests so
  call order, retry behavior, audit rows, and translation can be verified
  deterministically.

## Testing Rules

- Test domain and service behavior without HTTP or real infrastructure when the
  boundary permits it.
- Test routers through observable request, response, and documented error
  behavior.
- When one large test module covers independent responsibilities, split it by
  user-visible operation or application workflow after implementation
  boundaries are stable.

## Refactoring and Verification

- Prefer incremental extraction over rewriting an entire workflow. Preserve
  observable API and domain behavior and keep focused tests passing after each
  extraction.
- Define refactoring success by clearer responsibilities, narrower interfaces,
  explicit dependencies, and preserved behavior, not by a target file length.
- Before extracting code, identify the current owners of validation, domain
  policy, orchestration, transactions, persistence, and transport conversion.
  Preserve or deliberately improve those ownership boundaries.
- A responsibility-preserving refactor does not require a domain-document or
  OpenAPI update. If behavior, ownership, invariants, workflow semantics, or
  consumer-facing API behavior changes, update the required authoritative
  contract in the same change through the repository's assigned workflow.
