# Feature Ticket Queue Design

## Goal

Add a repository-local workflow that turns an explicitly requested feature idea
into an implementation-ready ticket. A ticket enters the queue only after the
user approves both a Superpowers design document and its detailed implementation
plan.

The queue is a personal local tool for the `romance-agent` repository. It does
not automatically create, claim, start, or implement tickets.

## Scope

The change adds:

- an explicitly invoked `prepare-feature-ticket` repository skill;
- a Go CLI named `ra-ticket`;
- a repository-local SQLite ticket database;
- ticket registration, listing, inspection, FIFO selection, and lifecycle
  commands; and
- deterministic tests for the CLI, database behavior, and skill workflow.

The change does not add a product UI, backend API operation, background worker,
automatic ticket claiming, automatic implementation, shared ticket storage, or
hard deletion. It does not change application domain behavior or any
`docs/domains/*.md` contract.

## Repository Layout

The implementation uses these paths:

```text
.agents/skills/prepare-feature-ticket/
├── SKILL.md
└── scripts/
    └── validate-skill.sh

tools/ra-ticket/
├── go.mod
├── cmd/ra-ticket/
└── internal/
    ├── command/
    └── store/

.local/
└── tickets.db
```

The root `mise.toml` pins the Go toolchain. The CLI uses the pure-Go
`modernc.org/sqlite` driver so building it does not require CGO. The repository
tracks source code, schema behavior, tests, and the skill, while `.local/` is
ignored by Git and holds the personal database.

## Explicit Skill Workflow

`prepare-feature-ticket` must run only when the user explicitly invokes it. An
ordinary request to discuss, design, or implement a feature must not silently
register a ticket.

The skill executes this workflow:

1. Run `superpowers:brainstorming` for the requested feature.
2. Produce the design document under `docs/superpowers/specs/`.
3. Complete the brainstorming self-review and obtain explicit user approval of
   the written design.
4. Run `superpowers:writing-plans` from the approved design.
5. Produce the detailed plan under `docs/superpowers/plans/`.
6. Review the written plan and obtain explicit user approval that it is ready
   for implementation.
7. Invoke `ra-ticket add` with the approved title, summary, design path, and plan
   path.
8. Return the newly created `ready` ticket to the user.

If either document is missing, incomplete, or unapproved, the workflow stops
without registering a ticket. Re-running the skill for a plan that is already
registered reports the existing ticket instead of creating a duplicate.

## Ticket Model

The SQLite `tickets` table stores:

| Field | Meaning |
| --- | --- |
| `id` | Monotonically increasing integer ticket identifier |
| `title` | Non-empty human-readable title |
| `summary` | Non-empty implementation scope summary |
| `spec_path` | Repository-relative path to the approved design document |
| `plan_path` | Repository-relative path to the approved implementation plan |
| `status` | `ready`, `in_progress`, `done`, or `cancelled` |
| `created_at` | UTC registration time |
| `updated_at` | UTC time of the latest state change |
| `started_at` | UTC time of the latest transition to `in_progress`, when present |
| `completed_at` | UTC transition time to `done`, when present |
| `cancelled_at` | UTC transition time to `cancelled`, when present |

`plan_path` is unique because one approved implementation plan represents one
queue item. Paths are normalized to repository-relative slash-separated paths
before storage. Both paths must resolve inside the current repository, and the
design and plan files must exist at registration time. The design must be under
`docs/superpowers/specs/`; the plan must be under `docs/superpowers/plans/`.

The CLI initializes the database and its parent directory on first use. SQLite
schema versioning supports ordered future migrations. Initialization and
migrations are idempotent.

## State Machine

The allowed transitions are:

```text
ready ──start──> in_progress ──done──> done
  │                  │
  └────cancel────────┴───────> cancelled

done ──────reopen──> ready
cancelled ─reopen──> ready
```

`start` sets `started_at`. `done` sets `completed_at`. `cancel` sets
`cancelled_at`. `reopen` resets all three lifecycle timestamps and returns the
ticket to `ready`. Every transition updates `updated_at` and occurs in one
transaction. A command that requests any other transition fails without
changing the ticket.

The system provides no hard-delete operation. Cancellation preserves local
history.

## CLI Contract

The CLI is invoked as `ra-ticket` and provides:

```sh
ra-ticket add --title TITLE --summary SUMMARY --spec PATH --plan PATH
ra-ticket list [--status STATUS] [--json]
ra-ticket next [--json]
ra-ticket show ID [--json]
ra-ticket start ID [--json]
ra-ticket done ID [--json]
ra-ticket cancel ID [--json]
ra-ticket reopen ID [--json]
```

All commands discover the repository root rather than depending on the caller's
current subdirectory. The database path is `<repository-root>/.local/tickets.db`.
Tests may override the database path through an explicit test-only command
dependency; normal user commands do not redirect the personal queue implicitly.

`list` orders tickets by `created_at ASC, id ASC` and may filter by one valid
status. `show` returns one ticket by ID.

`next` returns the oldest `ready` ticket using `created_at ASC, id ASC` and
never mutates it. The user must explicitly run `start ID` to transition that
ticket to `in_progress`. No queue command performs automatic claiming.

Human-readable output is the default. `--json` emits a stable JSON object for a
single ticket and a stable JSON array for `list`. Timestamps use RFC 3339 UTC
strings. JSON field names mirror the model's snake-case names.

## Errors and Exit Behavior

Commands validate all input before mutation and write diagnostic messages to
standard error. Failures use distinct non-zero exit categories for invalid
usage, missing repository or document paths, unknown tickets, invalid state
transitions, duplicate plans, empty queues, and database failures.

When `next` finds no `ready` ticket, it returns the empty-queue exit category.
Its JSON mode emits a machine-readable error object instead of a ticket. A
failed registration or transition leaves the database unchanged.

SQLite writes use transactions and a bounded busy timeout. This is a
single-user local tool, so it does not introduce worker leases or distributed
locking. SQLite still serializes writes safely if two local commands overlap.

## Skill and CLI Boundaries

The skill owns orchestration and approval gates. It derives the title and
summary from the approved artifacts, presents them to the user as part of the
plan review, and calls the CLI only after approval.

The CLI owns deterministic validation, persistence, querying, and state
transitions. It does not invoke agents, inspect whether prose has genuinely
been approved, or implement a ticket. Its registration preconditions make an
accidental incomplete entry difficult, while the skill supplies the human
approval guarantee.

No application frontend or backend imports the CLI module. The ticket database
is operational tooling state, not product or domain data.

## Verification Strategy

Go unit and integration tests use isolated temporary databases and cover:

- repository-root and database-path discovery;
- first-run schema creation and idempotent initialization;
- schema version handling;
- successful registration and path normalization;
- rejection of empty fields, missing files, paths outside the repository,
  misplaced artifacts, and duplicate plan paths;
- all valid lifecycle transitions;
- rejection and rollback of every invalid lifecycle transition;
- timestamp behavior for start, completion, cancellation, and reopening;
- FIFO ordering using both `created_at` and `id`;
- the guarantee that `next` never changes state or timestamps;
- empty-queue and unknown-ticket behavior;
- status filtering; and
- human-readable and JSON output contracts.

CLI integration tests execute commands against a temporary repository and
SQLite database. The skill validator checks the explicit-trigger requirement,
the ordered brainstorming and writing-plan gates, both user approvals, the
required `ra-ticket add` registration, and the prohibition on registration
before the plan is approved.

Final verification runs:

```sh
mise exec -- go test ./...
mise exec -- go vet ./...
.agents/skills/prepare-feature-ticket/scripts/validate-skill.sh
```

The Go commands run from `tools/ra-ticket/`.

## Acceptance Criteria

- Only explicit invocation of `prepare-feature-ticket` can initiate automatic
  ticket registration.
- Registration occurs only after the user approves a written design and a
  written detailed implementation plan.
- Registered tickets begin in `ready` and reference both existing approved
  artifacts.
- The local SQLite database is repository-specific and excluded from Git.
- `ra-ticket next` deterministically returns the oldest `ready` ticket and does
  not mutate it.
- Users can list, inspect, start, complete, cancel, and reopen tickets through
  validated state transitions.
- Duplicate plans, invalid paths, missing documents, and invalid transitions do
  not modify stored data.
- Human-readable and JSON output both support immediate implementation from the
  returned design and plan paths.
- The implementation introduces no UI, consumer API, background worker,
  automatic claiming behavior, or domain-contract change.
