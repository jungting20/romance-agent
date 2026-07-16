# Worldbuilding Edit and Add Design

## Context

The writing workspace at `/projects/$projectId/write` already exposes a
read-only `세계관 보기` context tab. Story Bible owns each world entry as a
stable identifier, a kind (`place`, `object`, or `rule`), a title, and a
description. The workspace response currently supplies that data, but there is
no operation for changing it and no backend project persistence implementation.

The requested feature lets an author revise existing worldbuilding facts and
add new facts without leaving the writing workspace. The author selected
project-scoped files, rather than a database, as the persistence mechanism.

## Goal

Allow an author to open one focused editor from `세계관 보기`, revise any
existing world entry, add one or more entries, validate the complete draft, and
save all accepted changes atomically to the project's Story Bible file.

## Requirements

- **REQ-WORLD-001:** The world context panel exposes an accessible
  `세계관 수정 및 추가` action.
- **REQ-WORLD-002:** Activating the action opens a Sheet that contains every
  existing world entry with editable kind, title, and description fields.
- **REQ-WORLD-003:** The Sheet lets the author append multiple unsaved entries
  with the same editable fields.
- **REQ-WORLD-004:** Saving trims titles and descriptions, rejects blank values,
  preserves existing entry identifiers, and assigns server-generated identifiers
  to additions.
- **REQ-WORLD-005:** A successful save replaces the visible world list with the
  server response and closes the editor. A failed save leaves the draft intact,
  explains the failure, and offers retry.
- **REQ-WORLD-006:** Closing a dirty editor requires confirmation before the
  unsaved draft is discarded. Closing an unchanged editor does not prompt.
- **REQ-WORLD-007:** The selected world tab and open editor are reconstructible
  from the URL. User-initiated open and close transitions create browser history
  entries so Back and Forward replay the visible state.
- **REQ-WORLD-008:** The backend persists each project's Story Bible in a JSON
  file and rejects a stale revision rather than overwriting a concurrent save.
- **REQ-WORLD-009:** The file update is atomic: validation and revision checks
  complete before a temporary file is replaced into the canonical path.
- **REQ-WORLD-010:** Desktop and mobile layouts provide the same editing and
  recovery behavior with keyboard-operable controls, visible focus, labels, and
  announced validation or request errors.

## User Experience

### Read mode

The existing world context panel keeps its compact cards. Its heading row gains
the `세계관 수정 및 추가` action. The action remains available when the list is
empty, so an empty Story Bible has an obvious recovery path.

### Editor Sheet

The action opens a Sheet labeled `세계관 수정 및 추가`. On desktop it uses a
right-side editing surface while the writing workspace remains visible. On
small screens it occupies the available width above the existing context
surface. The UI planner will set exact widths, spacing, and component choices
without changing this interaction contract.

Each row contains:

- a labeled kind control with `장소`, `사물`, and `규칙` choices;
- a labeled title input; and
- a labeled description textarea.

Existing entries and unsaved additions are visually distinguishable without
using color alone. `세계관 항목 추가` appends a blank row and moves focus to its
first field. Deletion and manual reordering are not present in this release.

`저장` submits all edited existing entries and additions as one operation.
While it is pending, duplicate submission is disabled. Inline field messages
identify every invalid title or description. A request-level alert handles
conflict, missing project, unreadable file, and unexpected failures while
preserving the draft.

If the editor is dirty, its close button, Escape interaction, overlay click,
and browser navigation first expose a discard confirmation. Confirming discard
closes the editor; cancelling returns focus to the editing surface. Successful
save closes without confirmation and returns focus to the launch action.

## URL State

This feature builds on the repository's approved workspace-tab URL design.
The canonical search state is:

```text
tab = manuscript | characters | world
panel = world-editor
```

The manuscript default omits `tab`. The world editor canonical URL includes
both `tab=world` and `panel=world-editor`. Opening the editor from another
context first selects world and records one canonical navigation entry. Closing
the editor removes `panel` while retaining `tab=world`.

An unsupported `panel`, or `panel=world-editor` without the world tab, is
canonicalized with replacement navigation. A direct canonical URL opens the
same Sheet after required server data is available. Transient form values and
discard-confirmation visibility remain local state and are not encoded in the
URL.

## Domain Design

Story Bible remains the sole owner of world entries. Its contract gains two
use cases:

1. **Revise world entries:** update kind, title, and description for known
   identifiers without changing those identifiers.
2. **Add world entries:** create project-unique identifiers for validated new
   entries and append them to the Story Bible.

Titles and descriptions are normalized by trimming surrounding whitespace and
must remain non-empty. Kinds remain limited to place, object, and rule. A save
must not silently delete entries, mutate characters, or alter Manuscript scene
references. The application use case coordinates persistence but does not move
ownership out of Story Bible.

`docs/domains/story-bible.md` changes with the implementation. The context map
does not change because no domain relationship or dependency direction changes.

## API Design

The OpenAPI agent will define the exact OpenAPI 3.1 shapes and operation IDs.
The approved semantic baseline must provide:

- a project-scoped Story Bible read operation returning the current Story Bible
  and its revision; and
- one command-style world-entry save operation accepting the expected revision,
  complete replacement values for known entries, and additions without
  identifiers.

The save response returns the authoritative Story Bible and incremented
revision so the frontend can update its TanStack Query cache without guessing
server-generated IDs.

The operation distinguishes malformed input, field validation failures,
project or Story Bible absence, revision conflict, and unexpected persistence
failure. Existing-entry identifiers not found in the current Story Bible are a
validation error. The request cannot remove omitted entries or modify
characters.

Only the OpenAPI agent authors `docs/api/openapi.yaml`. Frontend and backend
work begins from the same exact main-agent-approved baseline.

## Persistence Design

The backend stores one canonical file per project beneath a configurable data
root, using a layout equivalent to:

```text
<data-root>/projects/<project-id>/story-bible.json
```

The file contains a schema version, a monotonically increasing Story Bible
revision, and the Story Bible value. The HTTP router delegates to a Story Bible
service; the service applies domain validation and commands; a repository owns
path safety, serialization, locking, and atomic replacement.

Project identifiers are treated as identifiers, never as trusted path
fragments. The repository prevents traversal outside the configured data root.
It takes a per-project filesystem lock, reads and verifies the current revision,
writes a fully serialized temporary file in the destination directory, flushes
it, and atomically replaces the canonical file. Tests use an injected temporary
data root. Runtime data is not committed to Git.

This feature does not introduce a database, an ORM, or a general-purpose
project repository. It implements only the Story Bible file boundary required
for worldbuilding reads and writes. Other currently unimplemented project API
operations remain outside scope.

## Frontend Architecture and Data Flow

The page continues to compose the workspace. Story Bible server state is owned
by TanStack Query through a focused query and mutation feature; React
components do not call HTTP directly.

The flow is:

1. The workspace route validates and canonicalizes tab and editor search state.
2. The page reads the current Story Bible query result and gives it to the
   read-only panel.
3. Opening the editor creates a local draft copied from the authoritative query
   value.
4. The editor emits a typed save command containing known-entry revisions,
   additions, and expected revision.
5. On success, the mutation replaces the Story Bible query cache with the
   response and closes the URL-owned Sheet.
6. On failure, the Sheet keeps its draft and renders the mapped error state.

Domain normalization and validation are pure functions in the Story Bible
module and are covered independently. The backend repeats authoritative
validation because frontend validation is for feedback, not trust.

MSW types, handlers, and mock storage follow the exact approved OpenAPI
baseline. They model successful saves, validation errors, missing data, and
revision conflict. MSW remains a contract-aligned development and test adapter;
the backend file repository is the durable production boundary.

## Error and Concurrency Behavior

- Client validation prevents submission and focuses the first invalid field.
- A revision conflict preserves the entire draft and tells the author that the
  stored Story Bible changed. It offers `최신 세계관 불러오기`, which requires
  discard confirmation and then replaces the draft with a newly fetched
  authoritative value. The initial release does not retry a stale revision or
  attempt an automatic field merge.
- A missing project or Story Bible reports that the data can no longer be
  edited and leaves navigation back to read mode available.
- A file read, lock, serialization, or atomic replacement failure returns the
  contract's persistence-safe error and never reports success.
- No failure clears the editor draft automatically.

The UI plan may refine exact recovery copy, but it may not introduce silent
overwrite, silent discard, or partial success.

## Testing and Verification

### Focused coverage

- Story Bible unit tests cover trimming, blank-field rejection, kind
  validation, identifier preservation, addition, and input immutability.
- Frontend component and query tests cover opening from the world panel,
  editing, adding multiple rows, accessible field errors, pending submission,
  success, retryable failures, conflicts, discard confirmation, cache updates,
  direct URLs, canonicalization, and Back/Forward.
- API adapter and MSW tests verify the approved method, path, payload, response,
  and consumed errors.
- Backend service and repository tests cover validation, new identifiers,
  revision increments, stale revisions, path traversal prevention, atomic
  replacement, and persistence across repository re-instantiation.
- Backend API tests cover every declared success and error status for the new
  operations.
- Playwright covers the critical desktop and mobile edit/add/save flows,
  keyboard interaction, reload from persisted server data where the configured
  test environment supports the backend, and a meaningful save failure.

### Required commands

From `frontend/`:

```sh
mise exec -- pnpm check
mise exec -- pnpm build
```

From `backend/`:

```sh
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

The OpenAPI contract is validated from `frontend/` with:

```sh
mise exec -- pnpm api:lint
```

Focused Vitest, Playwright, pytest, and contract checks run during
implementation before the full application checks.

## Ownership and Delivery Pipeline

- `ui-planner` exclusively authors
  `frontend/docs/ui-plans/worldbuilding-edit-add.md` from this approved design.
- `openapi` exclusively authors `docs/api/openapi.yaml` after UI-plan approval.
- `frontend` owns assigned frontend implementation, unit/component tests, MSW,
  and any assigned frontend engineering-rule update.
- `backend` owns assigned backend implementation, tests, and any assigned
  backend engineering-rule update.
- The main agent retains `docs/domains/story-bible.md` unless one implementer is
  explicitly assigned it, approves the UI plan and OpenAPI baseline, integrates
  the work, triages findings, and performs final verification.
- The configured Playwright planner and generator run after frontend
  implementation and before application review.
- `frontend-review` and `backend-review` inspect stopped implementations
  read-only; accepted findings return to the owning implementer.

## Exclusions

- Deleting or reordering world entries.
- Editing characters, manuscript references, project metadata, or the story
  concept.
- Automatic conflict merging or multi-user presence.
- Database, ORM, cloud object storage, file import/export, or attachment
  support.
- Implementing unrelated existing project or manuscript backend operations.
- Generating worldbuilding content with an LLM.

## Accepted Constraints and Risks

- File persistence is appropriate for the selected single-service deployment
  but does not provide database-style querying or horizontal multi-node
  coordination. A later multi-node deployment requires a different repository
  adapter while preserving the domain and API behavior.
- The repository currently lacks the full project backend used by all workspace
  operations. This feature supplies the durable Story Bible boundary only; the
  existing MSW adapter continues to support the complete frontend development
  workspace until the remaining backend operations are implemented.
- The approved workspace-tab URL design is a prerequisite for editor URL state
  and may be implemented in the same frontend change where the current branch
  has only its design and plan records.

## Approval Record

The user approved the implementation brief on 2026-07-15, including the
project-scoped file persistence decision, Sheet-based edit/add flow,
command-style atomic save, API and cross-stack scope, domain synchronization,
and explicit exclusions above.
