# Story Bible Domain Boundary Refactor Design

## Context

The Story Bible backend currently supports project-scoped reads and atomic
world-entry updates through `getStoryBible` and `saveWorldEntries`. Its HTTP
behavior, OpenAPI contract, revision checks, JSON persistence format, path
safety, locking, and atomic replacement are covered by passing tests.

The implementation nevertheless places domain models, application commands,
application errors, a repository port, and orchestration in one service module.
The file repository imports those types from the service module, and the router
constructs the concrete repository. Domain objects are frozen dataclasses but
do not enforce their own invariants, so invalid objects can be created when a
caller bypasses the current command-validation path.

## Goal

Refactor `backend/apps/story_bible` so domain invariants and state transitions
have an explicit domain owner, application orchestration depends on focused
ports, persistence depends on domain types rather than service internals, and
runtime composition is kept outside the HTTP router.

The refactor must preserve all existing consumer-visible API behavior and the
canonical Story Bible JSON representation.

## Scope

The refactor covers the existing Story Bible read and world-entry save
operations only. It reorganizes domain models, application commands and ports,
service orchestration, repository conversion, runtime dependency composition,
and their tests.

It does not implement other Story Bible use cases that are present in the
domain contract but absent from the current API and backend slice.

## Architecture

The package will use the following responsibility boundaries:

```text
apps/story_bible/
├── domain/
│   ├── models.py          # Character, WorldEntry, StoryBible
│   └── errors.py          # Domain invariant failures
├── service/
│   ├── story_bible.py     # Read and save application workflows
│   ├── commands.py        # Application commands and field-error values
│   └── ports.py           # Repository and identifier-generation ports
├── repository/
│   └── story_bible.py     # JSON conversion, locking, and atomic replacement
├── router/
│   ├── story_bible.py     # HTTP translation and error mapping
│   └── dependencies.py    # FastAPI dependency provider
└── schemas/
    └── story_bible.py     # Pydantic transport schemas
```

Small modules may be combined when implementation shows that a separate file
would contain no independent responsibility. The ownership and dependency
directions above are required even if the exact file count is reduced.

### Domain

`Character`, `WorldEntry`, and `StoryBible` move to `domain/`. Domain creation
enforces the invariants that are valid independently of HTTP, persistence, or a
specific application command.

- `Character` requires a non-empty identifier and name. The existing supported
  role remains `protagonist`; desire and hidden feeling retain their current
  allowance for empty strings.
- `WorldEntry` requires a non-empty identifier, a supported kind, and title and
  description values that remain non-empty after surrounding whitespace is
  trimmed. The normalized values are stored on the domain object.
- `StoryBible` requires a non-empty project identifier and rejects duplicate
  character or world-entry identifiers within the aggregate.
- The aggregate world-entry change operation preserves all characters, keeps
  existing world-entry identifiers and ordering, leaves omitted entries
  unchanged, and appends additions in request order with non-conflicting IDs.

Domain failures contain domain meaning and do not contain HTTP status codes,
Pydantic details, JSON keys, or request-array field paths.

### Application Service and Ports

The service coordinates the workflow without reconstructing aggregate-owned
state. It:

1. loads the current Story Bible snapshot through a repository port;
2. rejects any exact revision mismatch;
3. checks command-level duplicate update IDs and unknown update targets;
4. obtains collision-free identifiers for additions through an injected typed
   identifier-generation dependency;
5. invokes the aggregate world-entry change operation; and
6. calls repository compare-and-replace with the original expected revision.

The service owns application commands, field-error paths, workflow
preconditions, and translation from domain failures into the existing
`InvalidWorldEntriesError` shape. It remains independent of FastAPI, Pydantic,
filesystem APIs, environment variables, UUID implementation, and process
globals.

The repository port exposes only the current consumer needs: load a project
snapshot and replace it when the exact expected revision still matches. The
identifier dependency exposes project-scoped ID generation without mirroring
the UUID library.

### Repository

The file repository translates between the canonical JSON representation and
domain objects. It retains the existing schema version and envelope fields.
Decode-time domain failures are translated into `StoryBiblePersistenceError`
because invalid stored bytes are a persistence-boundary failure to callers.

The repository continues to own:

- configured-root path resolution and traversal or symlink escape rejection;
- exact schema and stored-project validation;
- a project-local sibling lock;
- re-reading the canonical file while holding the lock;
- exact lower-or-higher revision conflict detection;
- same-directory temporary-file serialization, flush, and `fsync`;
- atomic `os.replace`; and
- cleanup of only the temporary file created by the failed operation.

The repository must not normalize invalid application input or decide
world-entry update policy.

### Router and Composition

The router remains responsible for transport-to-command conversion,
service invocation, response-schema conversion, and translation of defined
application failures into the approved HTTP responses. The existing unexpected
failure handling remains at this outer HTTP boundary and continues to return
the documented internal-error response without exposing exception details.

The router no longer imports or constructs `FileStoryBibleRepository` and does
not read `ROMANCE_AGENT_DATA_ROOT`. A composition boundary associated with
application startup or FastAPI dependency provisioning combines the configured
data root, file repository, UUID-backed identifier generator, and Story Bible
service. Tests can continue overriding the service dependency without real
filesystem or process configuration.

## Data Flow

For `getStoryBible`, the router passes the project identifier to the service,
the service loads the snapshot through its port, and the router translates the
result into the unchanged response schema.

For `saveWorldEntries`, the flow is:

1. Pydantic validates JSON syntax, strict transport types, required fields,
   extra fields, and the supported kind enum.
2. The router converts the request into an application command.
3. The service loads the current snapshot and verifies the exact expected
   revision.
4. The service validates command-wide workflow preconditions and allocates
   addition IDs.
5. The aggregate normalizes and atomically applies all valid domain changes.
6. The repository locks, re-reads, compares the expected revision, writes the
   replacement, and returns the incremented authoritative snapshot.
7. The router converts that snapshot into the unchanged HTTP response.

No layer returns a partial result. A failure before replacement leaves the
canonical Story Bible unchanged.

## Error Semantics

The refactor preserves these externally observable mappings:

- malformed transport input to `400 MALFORMED_REQUEST`;
- missing Story Bible to `404 STORY_BIBLE_NOT_FOUND`;
- any exact expected-revision mismatch to
  `409 STORY_BIBLE_REVISION_CONFLICT`;
- blank values, duplicate update IDs, or unknown update IDs to
  `422 INVALID_WORLD_ENTRIES` with the existing field paths and messages; and
- composition, filesystem, serialization, and unexpected failures to
  `500 INTERNAL_ERROR`.

Domain errors are translated at the application boundary when field-level
application context is required. Persistence decode errors are translated at
the repository boundary. HTTP responses are constructed only at the router or
global FastAPI exception boundary.

## Compatibility Requirements

The following are immutable acceptance criteria for this refactor:

- Keep the existing route paths, methods, operation IDs, status codes, request
  fields, response fields, aliases, and user-facing error messages.
- Keep the `story-bible.json` path, `schemaVersion`, envelope keys, nested keys,
  list ordering, and revision semantics.
- Preserve accepted existing files without migration or schema-version change.
- Preserve all characters and omitted world entries during a world-entry save.
- Preserve updated entry IDs and append new entries in request order.
- Preserve conflict behavior for both lower and higher expected revisions.
- Preserve canonical-file bytes on failed validation, revision comparison,
  serialization, locking, or replacement.

No compatibility facade is required for internal Python import paths. Source
and tests will be updated together to import types from their authoritative new
owners.

## Testing and Verification

Domain tests will cover:

- rejection of empty character, world-entry, and project identifiers;
- supported character roles and world-entry kinds;
- trimming and blank rejection for world-entry title and description;
- duplicate aggregate identifiers;
- immutable aggregate changes that preserve characters, omitted entries,
  existing IDs, and order; and
- rejection of colliding addition IDs.

Service tests will cover revision checks, duplicate and unknown updates,
collision-free ID allocation, aggregate invocation results, a single
compare-and-replace call, and unchanged existing error details.

Repository tests will retain coverage for round-trip persistence, malformed
documents, project mismatch, path and symlink escape, exact revision conflicts,
locking, same-directory temporary files, `fsync`, atomic replacement, and
failure cleanup. They will also verify translation of invalid stored domain
values into persistence errors.

API tests will preserve all current success and documented-error assertions,
operation IDs, strict request handling, dependency override behavior, and
composition-failure mapping.

Required backend verification from `backend/` is:

```sh
mise exec -- uv run pytest tests/story_bible
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

## Documentation Impact

This is a responsibility-preserving refactor. It does not change domain
meaning, relationships, API behavior, or persistence semantics, so it does not
edit `docs/domains/story-bible.md`, `docs/domains/README.md`, or
`docs/api/openapi.yaml`.

The existing `backend/README.md` already documents the target domain, router,
service, repository, and schemas package responsibilities. It requires no
structural map change unless implementation departs from the architecture
defined here.

## Exclusions

- Confirmed relationship or location event models and APIs.
- Narrative Memory candidate confirmation.
- Scene-context selection.
- New or changed consumer-facing API operations.
- JSON migration or schema-version changes.
- Database, ORM, remote storage, or asynchronous persistence.
- Frontend changes.
- Changes to existing error copy.
- Generic base repositories, services, schemas, exception hierarchies, or a
  general-purpose dependency-injection container.

## Delivery Boundary

Implementation affects `backend/apps/story_bible`, its focused tests,
composition wiring in `backend/main.py` or a focused backend composition
module, and formatting needed for touched Story Bible files. It must preserve
unrelated user changes and avoid unrelated backend refactoring.

Because this is substantial backend work, implementation is assigned to the
backend implementation agent and receives a read-only backend review after
editing stops. No OpenAPI agent or frontend agent is required because the
consumer contract and frontend behavior do not change.

## Approval Record

The user approved the behavior-preserving refactor scope on 2026-07-20. The
approved direction uses a targeted Story Bible aggregate refactor rather than
a file-only move or a full generic hexagonal rewrite. The user separately
approved the architecture, data flow and invariant ownership, and testing,
compatibility, and exclusion boundaries before this document was written.
