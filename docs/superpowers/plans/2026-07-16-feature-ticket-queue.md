# Feature Ticket Queue Implementation Plan

> **Historical baseline:** This plan records the initial queue implementation.
> Its read-only `next` requirements were superseded on 2026-07-16 by the
> atomic claim behavior in
> `docs/superpowers/specs/2026-07-16-feature-ticket-queue-design.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicitly invoked planning skill and a repository-local Go/SQLite CLI that registers implementation-ready feature tickets and manages their lifecycle without automatic claiming.

**Architecture:** A standalone Go module under `tools/ra-ticket` owns repository discovery, SQLite persistence, ticket validation, state transitions, and human/JSON CLI output. The repository skill `prepare-feature-ticket` orchestrates Superpowers brainstorming and implementation planning, obtains both user approvals, then calls the deterministic CLI to register one `ready` ticket in the Git-ignored `.local/tickets.db` database.

**Tech Stack:** Go 1.26.5, `database/sql`, `modernc.org/sqlite` v1.53.0, SQLite, Agent Skills Markdown, POSIX shell.

## Global Constraints

- This is personal tooling for the `romance-agent` repository; do not add shared or remote storage.
- Do not add a UI, consumer-facing API, backend service, background worker, automatic ticket claiming, or automatic implementation.
- Do not change `docs/api/openapi.yaml`, frontend or backend application code, or `docs/domains/*.md`.
- Preserve the existing user modification in `frontend/src/modules/story-bible/ui/story-context-panel.tsx`.
- `prepare-feature-ticket` registers a ticket only after explicit invocation and explicit approval of both the design document and implementation plan.
- `ra-ticket next` is FIFO over `ready` tickets and must never mutate ticket state or timestamps.
- Store the local database at `.local/tickets.db`; ignore `.local/` in Git.
- Store timestamps as RFC 3339 Nano UTC text.
- Reject hard deletion; preserve history through `cancelled`.
- The current feature is the bootstrap that creates the queue. Do not seed an already-implemented bootstrap ticket after completion.
- Run Go commands from `tools/ra-ticket/` unless a step explicitly says otherwise.

## File Structure

```text
mise.toml                                      # pins Go 1.26.5
.gitignore                                     # ignores repository-local queue state
README.md                                      # documents setup and management commands
.agents/skills/prepare-feature-ticket/
├── SKILL.md                                   # explicit-only design/plan/register workflow
└── scripts/validate-skill.sh                  # structural workflow contract
tools/ra-ticket/
├── go.mod                                     # standalone Go module and SQLite dependency
├── go.sum                                     # resolved SQLite dependency checksums
├── cmd/ra-ticket/main.go                      # process entry point and repository discovery
└── internal/
    ├── repository/
    │   ├── root.go                            # repository-root and DB-path discovery
    │   └── root_test.go
    ├── ticket/
    │   ├── model.go                           # statuses, ticket data, actions, typed errors
    │   ├── store.go                           # schema, registration, queries, transitions
    │   └── store_test.go
    └── cli/
        ├── run.go                             # argument parsing, exit mapping, output
        └── run_test.go
```

---

### Task 1: Establish the Go Tool and Repository Discovery

**Files:**
- Modify: `mise.toml`
- Modify: `.gitignore`
- Create: `tools/ra-ticket/go.mod`
- Create: `tools/ra-ticket/internal/repository/root.go`
- Test: `tools/ra-ticket/internal/repository/root_test.go`

**Interfaces:**
- Consumes: a starting directory supplied by the process entry point or tests.
- Produces: `repository.FindRoot(start string) (string, error)` and `repository.DatabasePath(root string) string`.

- [ ] **Step 1: Add failing repository discovery tests**

Create `tools/ra-ticket/internal/repository/root_test.go`:

```go
package repository

import (
	"os"
	"path/filepath"
	"testing"
)

func TestFindRootFromNestedDirectory(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, ".git"), 0o755); err != nil {
		t.Fatal(err)
	}
	nested := filepath.Join(root, "tools", "ra-ticket")
	if err := os.MkdirAll(nested, 0o755); err != nil {
		t.Fatal(err)
	}

	got, err := FindRoot(nested)
	if err != nil {
		t.Fatal(err)
	}
	if got != root {
		t.Fatalf("FindRoot() = %q, want %q", got, root)
	}
}

func TestFindRootAcceptsWorktreeGitFile(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, ".git"), []byte("gitdir: /tmp/example\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	got, err := FindRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	if got != root {
		t.Fatalf("FindRoot() = %q, want %q", got, root)
	}
}

func TestFindRootRejectsDirectoryOutsideRepository(t *testing.T) {
	_, err := FindRoot(t.TempDir())
	if err == nil {
		t.Fatal("FindRoot() error = nil, want repository-not-found error")
	}
}

func TestDatabasePathUsesLocalDirectory(t *testing.T) {
	root := filepath.Join(string(filepath.Separator), "repo")
	want := filepath.Join(root, ".local", "tickets.db")
	if got := DatabasePath(root); got != want {
		t.Fatalf("DatabasePath() = %q, want %q", got, want)
	}
}
```

- [ ] **Step 2: Create the module and verify RED**

Add this exact entry to the root `mise.toml` `[tools]` table:

```toml
go = "1.26.5"
```

Create `tools/ra-ticket/go.mod`:

```go
module romance-agent/tools/ra-ticket

go 1.26.0
```

From `tools/ra-ticket/`, run:

```sh
mise exec -- go test ./internal/repository -run 'TestFindRoot|TestDatabasePath' -v
```

Expected: compilation fails because `FindRoot` and `DatabasePath` are
undefined.

- [ ] **Step 3: Implement repository discovery**

Create `tools/ra-ticket/internal/repository/root.go`:

```go
package repository

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

var ErrNotFound = errors.New("repository root not found")

func FindRoot(start string) (string, error) {
	current, err := filepath.Abs(start)
	if err != nil {
		return "", fmt.Errorf("resolve start directory: %w", err)
	}

	for {
		if _, err := os.Stat(filepath.Join(current, ".git")); err == nil {
			return current, nil
		} else if !errors.Is(err, os.ErrNotExist) {
			return "", fmt.Errorf("inspect repository marker: %w", err)
		}

		parent := filepath.Dir(current)
		if parent == current {
			return "", ErrNotFound
		}
		current = parent
	}
}

func DatabasePath(root string) string {
	return filepath.Join(root, ".local", "tickets.db")
}
```

- [ ] **Step 4: Ignore local state and verify GREEN**

Append this exact entry to root `.gitignore`:

```gitignore
.local/
```

Run from `tools/ra-ticket/`:

```sh
mise exec -- gofmt -w internal/repository/root.go internal/repository/root_test.go
mise exec -- go test ./internal/repository -v
git diff --check -- ../../mise.toml ../../.gitignore go.mod internal/repository
```

Expected: all repository tests pass, `go mod tidy` makes no further changes,
and `git diff --check` exits `0`.

- [ ] **Step 5: Commit the tool foundation**

```sh
git add ../../mise.toml ../../.gitignore go.mod internal/repository
git commit -m "build: establish feature ticket CLI"
```

---

### Task 2: Create the SQLite Schema and Register Tickets

**Files:**
- Create: `tools/ra-ticket/internal/ticket/model.go`
- Create: `tools/ra-ticket/internal/ticket/store.go`
- Create: `tools/ra-ticket/go.sum`
- Modify: `tools/ra-ticket/go.mod`
- Test: `tools/ra-ticket/internal/ticket/store_test.go`

**Interfaces:**
- Consumes: repository root, SQLite path, deterministic clock, and `ticket.CreateInput`.
- Produces: `ticket.Open`, `(*Store).Close`, and `(*Store).Add`; the `Ticket`, `Status`, `Action`, and sentinel error contract used by Tasks 3 and 4.

- [ ] **Step 1: Define model and registration tests**

Create `tools/ra-ticket/internal/ticket/model.go`:

```go
package ticket

import (
	"errors"
	"time"
)

type Status string

const (
	StatusReady      Status = "ready"
	StatusInProgress Status = "in_progress"
	StatusDone       Status = "done"
	StatusCancelled  Status = "cancelled"
)

type Action string

const (
	ActionStart  Action = "start"
	ActionDone   Action = "done"
	ActionCancel Action = "cancel"
	ActionReopen Action = "reopen"
)

var (
	ErrNotFound          = errors.New("ticket not found")
	ErrDuplicatePlan     = errors.New("implementation plan already registered")
	ErrEmptyQueue        = errors.New("no ready tickets")
	ErrInvalidTransition = errors.New("invalid ticket status transition")
	ErrInvalidArtifact   = errors.New("invalid ticket artifact")
)

type Ticket struct {
	ID          int64      `json:"id"`
	Title       string     `json:"title"`
	Summary     string     `json:"summary"`
	SpecPath    string     `json:"spec_path"`
	PlanPath    string     `json:"plan_path"`
	Status      Status     `json:"status"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
	StartedAt   *time.Time `json:"started_at"`
	CompletedAt *time.Time `json:"completed_at"`
	CancelledAt *time.Time `json:"cancelled_at"`
}

type CreateInput struct {
	Title    string
	Summary  string
	SpecPath string
	PlanPath string
}
```

Create `tools/ra-ticket/internal/ticket/store_test.go` with shared helpers and
the first registration cases:

```go
package ticket

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"
)

var fixedNow = time.Date(2026, 7, 16, 12, 0, 0, 123, time.UTC)

func newTestStore(t *testing.T) (*Store, string) {
	t.Helper()
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, ".git"), 0o755); err != nil {
		t.Fatal(err)
	}
	store, err := Open(context.Background(), root, filepath.Join(root, ".local", "tickets.db"), func() time.Time { return fixedNow })
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = store.Close() })
	return store, root
}

func writeArtifacts(t *testing.T, root, name string) (string, string) {
	t.Helper()
	spec := filepath.Join(root, "docs", "superpowers", "specs", name+"-design.md")
	plan := filepath.Join(root, "docs", "superpowers", "plans", name+".md")
	for _, path := range []string{spec, plan} {
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte("# Approved\n"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return spec, plan
}

func TestOpenCreatesSchemaAndAddRegistersReadyTicket(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "search")

	got, err := store.Add(context.Background(), CreateInput{
		Title: "Search story bible",
		Summary: "Add indexed story-bible search.",
		SpecPath: spec,
		PlanPath: plan,
	})
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != StatusReady || got.ID != 1 {
		t.Fatalf("Add() = %#v", got)
	}
	if got.SpecPath != "docs/superpowers/specs/search-design.md" || got.PlanPath != "docs/superpowers/plans/search.md" {
		t.Fatalf("stored paths = %q, %q", got.SpecPath, got.PlanPath)
	}
	if !got.CreatedAt.Equal(fixedNow) || !got.UpdatedAt.Equal(fixedNow) {
		t.Fatalf("timestamps = %s, %s", got.CreatedAt, got.UpdatedAt)
	}
}

func TestAddRejectsDuplicatePlanWithoutInserting(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "search")
	input := CreateInput{Title: "Search", Summary: "Search stories.", SpecPath: spec, PlanPath: plan}
	if _, err := store.Add(context.Background(), input); err != nil {
		t.Fatal(err)
	}
	_, err := store.Add(context.Background(), input)
	if !errors.Is(err, ErrDuplicatePlan) {
		t.Fatalf("Add() error = %v, want ErrDuplicatePlan", err)
	}
}

func TestAddRejectsInvalidArtifacts(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "search")
	outside := filepath.Join(t.TempDir(), "outside.md")
	if err := os.WriteFile(outside, []byte("outside"), 0o644); err != nil {
		t.Fatal(err)
	}

	cases := []CreateInput{
		{Title: "", Summary: "summary", SpecPath: spec, PlanPath: plan},
		{Title: "title", Summary: "", SpecPath: spec, PlanPath: plan},
		{Title: "title", Summary: "summary", SpecPath: filepath.Join(root, "missing.md"), PlanPath: plan},
		{Title: "title", Summary: "summary", SpecPath: spec, PlanPath: outside},
	}
	for _, input := range cases {
		if _, err := store.Add(context.Background(), input); !errors.Is(err, ErrInvalidArtifact) {
			t.Fatalf("Add(%#v) error = %v, want ErrInvalidArtifact", input, err)
		}
	}
}
```

- [ ] **Step 2: Run registration tests to verify RED**

```sh
mise exec -- go test ./internal/ticket -run 'TestOpen|TestAdd' -v
```

Expected: compilation fails because `Store` and `Open` are undefined.

- [ ] **Step 3: Implement schema initialization and registration**

Pin the approved SQLite driver before creating the store:

```sh
mise exec -- go get modernc.org/sqlite@v1.53.0
```

Expected: `go.mod` contains `modernc.org/sqlite v1.53.0` and `go.sum` contains
the resolved checksums.

Create `tools/ra-ticket/internal/ticket/store.go` with:

```go
package ticket

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "modernc.org/sqlite"
)

const schema = `
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    summary TEXT NOT NULL CHECK (length(trim(summary)) > 0),
    spec_path TEXT NOT NULL,
    plan_path TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('ready','in_progress','done','cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tickets_status_fifo
ON tickets(status, created_at, id);
PRAGMA user_version = 1;
`

type Store struct {
	db       *sql.DB
	root     string
	now      func() time.Time
}

func Open(ctx context.Context, root, databasePath string, now func() time.Time) (*Store, error) {
	if now == nil {
		now = time.Now
	}
	if err := os.MkdirAll(filepath.Dir(databasePath), 0o755); err != nil {
		return nil, fmt.Errorf("create ticket database directory: %w", err)
	}
	db, err := sql.Open("sqlite", databasePath)
	if err != nil {
		return nil, fmt.Errorf("open ticket database: %w", err)
	}
	db.SetMaxOpenConns(1)
	if _, err := db.ExecContext(ctx, "PRAGMA busy_timeout = 5000"); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("configure ticket database: %w", err)
	}
	var version int
	if err := db.QueryRowContext(ctx, "PRAGMA user_version").Scan(&version); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("read schema version: %w", err)
	}
	if version > 1 {
		_ = db.Close()
		return nil, fmt.Errorf("unsupported ticket schema version %d", version)
	}
	if version == 0 {
		if _, err := db.ExecContext(ctx, schema); err != nil {
			_ = db.Close()
			return nil, fmt.Errorf("initialize ticket schema: %w", err)
		}
	}
	return &Store{db: db, root: root, now: now}, nil
}

func (s *Store) Close() error { return s.db.Close() }

func (s *Store) Add(ctx context.Context, input CreateInput) (Ticket, error) {
	title := strings.TrimSpace(input.Title)
	summary := strings.TrimSpace(input.Summary)
	spec, err := s.artifactPath(input.SpecPath, filepath.Join("docs", "superpowers", "specs"))
	if err != nil || title == "" || summary == "" {
		return Ticket{}, ErrInvalidArtifact
	}
	plan, err := s.artifactPath(input.PlanPath, filepath.Join("docs", "superpowers", "plans"))
	if err != nil {
		return Ticket{}, ErrInvalidArtifact
	}
	now := s.now().UTC()
	stamp := now.Format(time.RFC3339Nano)
	result, err := s.db.ExecContext(ctx, `
INSERT INTO tickets(title, summary, spec_path, plan_path, status, created_at, updated_at)
VALUES (?, ?, ?, ?, 'ready', ?, ?)`, title, summary, spec, plan, stamp, stamp)
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE constraint failed: tickets.plan_path") {
			return Ticket{}, ErrDuplicatePlan
		}
		return Ticket{}, fmt.Errorf("insert ticket: %w", err)
	}
	id, err := result.LastInsertId()
	if err != nil {
		return Ticket{}, fmt.Errorf("read ticket id: %w", err)
	}
	return Ticket{ID: id, Title: title, Summary: summary, SpecPath: spec, PlanPath: plan, Status: StatusReady, CreatedAt: now, UpdatedAt: now}, nil
}

func (s *Store) artifactPath(input, requiredDirectory string) (string, error) {
	candidate := input
	if !filepath.IsAbs(candidate) {
		candidate = filepath.Join(s.root, candidate)
	}
	abs, err := filepath.Abs(candidate)
	if err != nil {
		return "", err
	}
	resolved, err := filepath.EvalSymlinks(abs)
	if err != nil {
		return "", err
	}
	rel, err := filepath.Rel(s.root, resolved)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", ErrInvalidArtifact
	}
	required := requiredDirectory + string(filepath.Separator)
	if !strings.HasPrefix(rel, required) || filepath.Ext(rel) != ".md" {
		return "", ErrInvalidArtifact
	}
	info, err := os.Stat(resolved)
	if err != nil || !info.Mode().IsRegular() {
		return "", ErrInvalidArtifact
	}
	return filepath.ToSlash(rel), nil
}

func parseTime(value string) (time.Time, error) {
	return time.Parse(time.RFC3339Nano, value)
}

func parseOptionalTime(value sql.NullString) (*time.Time, error) {
	if !value.Valid {
		return nil, nil
	}
	parsed, err := parseTime(value.String)
	if err != nil {
		return nil, err
	}
	return &parsed, nil
}
```

- [ ] **Step 4: Verify schema and registration GREEN**

```sh
mise exec -- gofmt -w internal/ticket/model.go internal/ticket/store.go internal/ticket/store_test.go
mise exec -- go test ./internal/ticket -run 'TestOpen|TestAdd' -v
mise exec -- go test ./... -v
mise exec -- go vet ./...
```

Expected: all commands pass.

- [ ] **Step 5: Commit registration persistence**

```sh
git add go.mod go.sum internal/ticket
git commit -m "feat: register implementation-ready tickets"
```

---

### Task 3: Add FIFO Queries and Validated Lifecycle Transitions

**Files:**
- Modify: `tools/ra-ticket/internal/ticket/store.go`
- Modify: `tools/ra-ticket/internal/ticket/store_test.go`

**Interfaces:**
- Consumes: ticket IDs, optional status filters, and `ticket.Action`.
- Produces: `Get(ctx, id)`, `List(ctx, filter)`, `Next(ctx)`, and `Transition(ctx, id, action)` with sentinel errors from `model.go`.

- [ ] **Step 1: Add failing query and transition tests**

Append tests that use the Task 2 helpers and assert these exact cases:

```go
func TestNextReturnsOldestReadyWithoutMutation(t *testing.T) {
	store, root := newTestStore(t)
	spec1, plan1 := writeArtifacts(t, root, "first")
	first, err := store.Add(context.Background(), CreateInput{Title: "First", Summary: "First summary", SpecPath: spec1, PlanPath: plan1})
	if err != nil { t.Fatal(err) }
	spec2, plan2 := writeArtifacts(t, root, "second")
	if _, err := store.Add(context.Background(), CreateInput{Title: "Second", Summary: "Second summary", SpecPath: spec2, PlanPath: plan2}); err != nil { t.Fatal(err) }

	got, err := store.Next(context.Background())
	if err != nil { t.Fatal(err) }
	if got.ID != first.ID || got.Status != StatusReady { t.Fatalf("Next() = %#v", got) }
	after, err := store.Get(context.Background(), first.ID)
	if err != nil { t.Fatal(err) }
	if after.Status != first.Status || !after.UpdatedAt.Equal(first.UpdatedAt) || after.StartedAt != nil {
		t.Fatalf("Next mutated ticket: before=%#v after=%#v", first, after)
	}
}

func TestNextReturnsEmptyQueueAfterReadyTicketsLeaveQueue(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "first")
	created, err := store.Add(context.Background(), CreateInput{Title: "First", Summary: "First summary", SpecPath: spec, PlanPath: plan})
	if err != nil { t.Fatal(err) }
	if _, err := store.Transition(context.Background(), created.ID, ActionStart); err != nil { t.Fatal(err) }
	if _, err := store.Next(context.Background()); !errors.Is(err, ErrEmptyQueue) {
		t.Fatalf("Next() error = %v, want ErrEmptyQueue", err)
	}
}

func TestLifecycleTransitionsAndTimestamps(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "flow")
	created, err := store.Add(context.Background(), CreateInput{Title: "Flow", Summary: "Flow summary", SpecPath: spec, PlanPath: plan})
	if err != nil { t.Fatal(err) }

	started, err := store.Transition(context.Background(), created.ID, ActionStart)
	if err != nil { t.Fatal(err) }
	if started.Status != StatusInProgress || started.StartedAt == nil { t.Fatalf("start = %#v", started) }

	done, err := store.Transition(context.Background(), created.ID, ActionDone)
	if err != nil { t.Fatal(err) }
	if done.Status != StatusDone || done.CompletedAt == nil { t.Fatalf("done = %#v", done) }

	reopened, err := store.Transition(context.Background(), created.ID, ActionReopen)
	if err != nil { t.Fatal(err) }
	if reopened.Status != StatusReady || reopened.StartedAt != nil || reopened.CompletedAt != nil || reopened.CancelledAt != nil {
		t.Fatalf("reopen = %#v", reopened)
	}
}

func TestInvalidTransitionDoesNotMutateTicket(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "flow")
	created, err := store.Add(context.Background(), CreateInput{Title: "Flow", Summary: "Flow summary", SpecPath: spec, PlanPath: plan})
	if err != nil { t.Fatal(err) }
	if _, err := store.Transition(context.Background(), created.ID, ActionDone); !errors.Is(err, ErrInvalidTransition) {
		t.Fatalf("Transition() error = %v, want ErrInvalidTransition", err)
	}
	after, err := store.Get(context.Background(), created.ID)
	if err != nil { t.Fatal(err) }
	if after.Status != StatusReady || !after.UpdatedAt.Equal(created.UpdatedAt) {
		t.Fatalf("invalid transition mutated ticket: %#v", after)
	}
}
```

Also add table-driven assertions for `ready -> cancelled`, `in_progress ->
cancelled`, `cancelled -> ready`, unknown IDs returning `ErrNotFound`, status
filtering, and FIFO tie-breaking by `id`.

- [ ] **Step 2: Run focused tests to verify RED**

```sh
mise exec -- go test ./internal/ticket -run 'TestNext|TestLifecycle|TestInvalid|TestList|TestGet' -v
```

Expected: compilation fails because `Next`, `Get`, `List`, and `Transition` do
not exist.

- [ ] **Step 3: Implement row scanning and queries**

Add these signatures to `store.go`:

```go
func (s *Store) Get(ctx context.Context, id int64) (Ticket, error)
func (s *Store) List(ctx context.Context, filter *Status) ([]Ticket, error)
func (s *Store) Next(ctx context.Context) (Ticket, error)
```

Use one shared `scanTicket(scanner interface{ Scan(...any) error })` helper for
the eleven selected columns. `Get` maps `sql.ErrNoRows` to `ErrNotFound`.
`Next` runs this exact selection and maps `sql.ErrNoRows` to `ErrEmptyQueue`:

```sql
SELECT id, title, summary, spec_path, plan_path, status,
       created_at, updated_at, started_at, completed_at, cancelled_at
FROM tickets
WHERE status = 'ready'
ORDER BY created_at ASC, id ASC
LIMIT 1
```

`List` validates a non-nil filter against the four status constants, applies
`WHERE status = ?` when present, always orders by `created_at ASC, id ASC`, and
returns an allocated empty slice rather than `nil`.

- [ ] **Step 4: Implement transactional transitions**

Add:

```go
func (s *Store) Transition(ctx context.Context, id int64, action Action) (Ticket, error)
```

Begin a transaction, select the current ticket, and permit only this map:

```go
var allowed = map[Action]map[Status]Status{
	ActionStart:  {StatusReady: StatusInProgress},
	ActionDone:   {StatusInProgress: StatusDone},
	ActionCancel: {StatusReady: StatusCancelled, StatusInProgress: StatusCancelled},
	ActionReopen: {StatusDone: StatusReady, StatusCancelled: StatusReady},
}
```

Set timestamps exactly as follows before updating all status and lifecycle
columns in one statement:

```go
switch action {
case ActionStart:
	ticket.StartedAt = &now
case ActionDone:
	ticket.CompletedAt = &now
case ActionCancel:
	ticket.CancelledAt = &now
case ActionReopen:
	ticket.StartedAt = nil
	ticket.CompletedAt = nil
	ticket.CancelledAt = nil
}
ticket.Status = target
ticket.UpdatedAt = now
```

Return `ErrNotFound` for an unknown ID and `ErrInvalidTransition` before any
update for an unknown action or disallowed source status. Commit before
returning the updated ticket; roll back on every error.

- [ ] **Step 5: Verify query and state behavior GREEN**

```sh
mise exec -- gofmt -w internal/ticket/store.go internal/ticket/store_test.go
mise exec -- go test ./internal/ticket -v
mise exec -- go test ./... -race
mise exec -- go vet ./...
```

Expected: all commands pass, including the race detector.

- [ ] **Step 6: Commit query and lifecycle behavior**

```sh
git add internal/ticket/store.go internal/ticket/store_test.go
git commit -m "feat: manage feature ticket lifecycle"
```

---

### Task 4: Expose the Human and JSON CLI Contract

**Files:**
- Create: `tools/ra-ticket/internal/cli/run.go`
- Test: `tools/ra-ticket/internal/cli/run_test.go`
- Create: `tools/ra-ticket/cmd/ra-ticket/main.go`
- Modify: `README.md`

**Interfaces:**
- Consumes: command arguments, output writers, a repository start directory, and the Task 3 store API.
- Produces: `cli.Run(ctx, args, stdout, stderr, dependencies) int` and the executable `ra-ticket` process.

- [ ] **Step 1: Add failing CLI contract tests**

Create `tools/ra-ticket/internal/cli/run_test.go`. Use a temporary repository,
real temporary SQLite database, and captured `bytes.Buffer` streams. Define:

```go
type harness struct {
	root   string
	stdout bytes.Buffer
	stderr bytes.Buffer
	deps   Dependencies
}

func newHarness(t *testing.T) *harness {
	t.Helper()
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, ".git"), 0o755); err != nil { t.Fatal(err) }
	return &harness{
		root: root,
		deps: Dependencies{
			StartDirectory: root,
			Now: func() time.Time { return time.Date(2026, 7, 16, 12, 0, 0, 0, time.UTC) },
		},
	}
}

func (h *harness) run(t *testing.T, args ...string) int {
	t.Helper()
	return Run(context.Background(), args, &h.stdout, &h.stderr, h.deps)
}
```

Add focused tests proving:

- `add --title Search --summary "Search story bible" --spec <path> --plan <path> --json` exits `0` and decodes to a `ready` ticket;
- `next --json` returns the first ready ticket and a following `show ID --json` proves it stayed `ready` with unchanged `updated_at`;
- empty `next --json` exits `ExitEmptyQueue` and emits `{"error":"no ready tickets","code":"empty_queue"}` to standard error;
- `list --status ready --json` emits a JSON array;
- `start`, `done`, `cancel`, and `reopen` call the correct transitions;
- malformed IDs exit `ExitUsage`;
- missing tickets exit `ExitNotFound`;
- duplicate plans exit `ExitDuplicate`;
- invalid transitions exit `ExitInvalidTransition`; and
- missing or misplaced artifacts exit `ExitValidation`.

- [ ] **Step 2: Run CLI tests to verify RED**

```sh
mise exec -- go test ./internal/cli -v
```

Expected: compilation fails because `Dependencies`, `Run`, and exit constants
are undefined.

- [ ] **Step 3: Implement command parsing and exit mapping**

Create `tools/ra-ticket/internal/cli/run.go` with these public definitions:

```go
type Dependencies struct {
	StartDirectory string
	Now            func() time.Time
}

const (
	ExitOK                = 0
	ExitDatabase          = 1
	ExitUsage             = 2
	ExitNotFound          = 3
	ExitInvalidTransition = 4
	ExitDuplicate         = 5
	ExitEmptyQueue        = 6
	ExitValidation        = 7
)

func Run(ctx context.Context, args []string, stdout, stderr io.Writer, dependencies Dependencies) int
```

`Run` must:

1. discover the repository with `repository.FindRoot`;
2. open `repository.DatabasePath(root)` with `ticket.Open`;
3. use a dedicated `flag.FlagSet` with output discarded for each subcommand;
4. require the exact `add` flags from the design;
5. parse positive base-10 integer IDs for state and `show` commands;
6. reject trailing positional arguments;
7. call the matching store method; and
8. map sentinel errors to the exit constants above using `errors.Is`.

Represent machine errors with:

```go
type errorOutput struct {
	Error string `json:"error"`
	Code  string `json:"code"`
}
```

Encode JSON through `json.NewEncoder` so output ends with one newline. Human
single-ticket output must include ID, status, title, summary, spec path, and
plan path. Human `list` output must print one tab-separated line per ticket in
`ID STATUS TITLE PLAN_PATH` order. Empty human lists print `No tickets.`.

- [ ] **Step 4: Add the process entry point**

Create `tools/ra-ticket/cmd/ra-ticket/main.go`:

```go
package main

import (
	"context"
	"os"
	"time"

	"romance-agent/tools/ra-ticket/internal/cli"
)

func main() {
	workingDirectory, err := os.Getwd()
	if err != nil {
		_, _ = os.Stderr.WriteString("determine working directory: " + err.Error() + "\n")
		os.Exit(cli.ExitDatabase)
	}
	os.Exit(cli.Run(context.Background(), os.Args[1:], os.Stdout, os.Stderr, cli.Dependencies{
		StartDirectory: workingDirectory,
		Now:            time.Now,
	}))
}
```

- [ ] **Step 5: Document setup and commands**

Append a `## Local feature ticket queue` section to root `README.md` that says
the queue is personal, `.local/tickets.db` is not shared, ticket creation is
normally performed by `$prepare-feature-ticket`, and `next` does not start a
ticket. Include these exact commands:

```sh
cd tools/ra-ticket
mise exec -- go build -o ../../.local/bin/ra-ticket ./cmd/ra-ticket
../../.local/bin/ra-ticket next
../../.local/bin/ra-ticket list --status ready
../../.local/bin/ra-ticket show 1
../../.local/bin/ra-ticket start 1
../../.local/bin/ra-ticket done 1
../../.local/bin/ra-ticket cancel 1
../../.local/bin/ra-ticket reopen 1
```

Also document `--json` for agent-readable output and explain that rebuilding
the ignored binary is required after CLI source changes.

- [ ] **Step 6: Verify the executable contract GREEN**

```sh
mise exec -- gofmt -w internal/cli/run.go internal/cli/run_test.go cmd/ra-ticket/main.go
mise exec -- go test ./internal/cli -v
mise exec -- go test ./... -race
mise exec -- go vet ./...
mise exec -- go build -o ../../.local/bin/ra-ticket ./cmd/ra-ticket
../../.local/bin/ra-ticket next --json
```

Expected: tests, vet, and build pass. On a fresh personal database, the final
command exits `6` and writes the `empty_queue` JSON error to standard error;
if the developer already has local tickets, it exits `0` and prints the oldest
ready ticket without changing it.

- [ ] **Step 7: Commit the CLI and usage documentation**

```sh
git add internal/cli cmd/ra-ticket ../../README.md
git commit -m "feat: expose feature ticket commands"
```

---

### Task 5: Add the Explicit Feature-Ticket Preparation Skill

**Files:**
- Create: `.agents/skills/prepare-feature-ticket/SKILL.md`
- Create: `.agents/skills/prepare-feature-ticket/scripts/validate-skill.sh`
- Test: `.agents/skills/prepare-feature-ticket/scripts/validate-skill.sh`

**Interfaces:**
- Consumes: an explicit `$prepare-feature-ticket` request, the feature idea, an approved design, a completed written implementation plan, and the built `ra-ticket` CLI.
- Produces: exactly one registered `ready` ticket after design approval and one explicit approval covering the written plan, title, and summary, or no ticket on cancellation/failure.

- [ ] **Step 1: Write the failing structural validator**

Create executable `.agents/skills/prepare-feature-ticket/scripts/validate-skill.sh`:

```sh
#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skill_file=${1:-"$script_dir/../SKILL.md"}

fail() {
  printf 'prepare-feature-ticket skill: FAIL: %s\n' "$1" >&2
  exit 1
}

[ -f "$skill_file" ] || fail "missing SKILL.md"

require() {
  marker=$1
  label=$2
  grep -Fq -- "$marker" "$skill_file" || fail "missing $label: $marker"
}

require 'name: prepare-feature-ticket' 'skill name'
require 'only when the user explicitly invokes' 'explicit invocation gate'
require 'superpowers:brainstorming' 'brainstorming stage'
require 'docs/superpowers/specs/' 'design artifact path'
require 'explicit approval of the written design' 'design approval gate'
require 'superpowers:writing-plans' 'implementation planning stage'
require 'docs/superpowers/plans/' 'plan artifact path'
require 'Derive a non-empty title' 'title derivation stage'
require 'Present the written implementation plan, title, and summary together' 'registration value presentation'
require 'one explicit approval covering all' 'joint plan and registration approval gate'
require 'Do not register' 'negative registration gate'
require 'ra-ticket add' 'registration command'
require '--json' 'machine-readable registration'
require 'ready' 'initial ticket status'

brainstorm_line=$(grep -n -F 'superpowers:brainstorming' "$skill_file" | head -1 | cut -d: -f1)
design_approval_line=$(grep -n -F 'explicit approval of the written design' "$skill_file" | head -1 | cut -d: -f1)
plan_line=$(grep -n -F 'superpowers:writing-plans' "$skill_file" | head -1 | cut -d: -f1)
title_line=$(grep -n -F 'Derive a non-empty title' "$skill_file" | head -1 | cut -d: -f1)
present_line=$(grep -n -F 'Present the written implementation plan, title, and summary together' "$skill_file" | head -1 | cut -d: -f1)
plan_approval_line=$(grep -n -F 'one explicit approval covering all' "$skill_file" | head -1 | cut -d: -f1)
register_line=$(grep -n -F 'ra-ticket add' "$skill_file" | head -1 | cut -d: -f1)

[ "$brainstorm_line" -lt "$design_approval_line" ] || fail 'design approval must follow brainstorming'
[ "$design_approval_line" -lt "$plan_line" ] || fail 'writing plan must follow design approval'
[ "$plan_line" -lt "$title_line" ] || fail 'title derivation must follow writing plan'
[ "$title_line" -lt "$present_line" ] || fail 'title and summary presentation must follow derivation'
[ "$present_line" -lt "$plan_approval_line" ] || fail 'joint approval must follow title and summary presentation'
[ "$plan_approval_line" -lt "$register_line" ] || fail 'registration must follow plan approval'

printf 'prepare-feature-ticket skill: OK\n'
```

Run:

```sh
chmod +x .agents/skills/prepare-feature-ticket/scripts/validate-skill.sh
.agents/skills/prepare-feature-ticket/scripts/validate-skill.sh
```

Expected: non-zero exit with `missing SKILL.md`.

- [ ] **Step 2: Write the skill workflow**

Create `.agents/skills/prepare-feature-ticket/SKILL.md` with concise frontmatter
whose description says it is used only when the user explicitly invokes
`$prepare-feature-ticket`, not for ordinary design or implementation requests.
The body must define this ordered workflow with the validator's exact marker
phrases:

1. Confirm the request is an explicit invocation and extract the feature idea.
2. Invoke `superpowers:brainstorming`; follow it completely through the design
   at `docs/superpowers/specs/` and explicit approval of the written design.
3. Invoke `superpowers:writing-plans`; produce the completed written implementation plan
   at `docs/superpowers/plans/`, review it, and preserve its path without
   requesting approval yet.
4. Derive a non-empty title and implementation-scope summary from the approved
   design and completed written plan.
5. Present the written implementation plan, title, and summary together, then
   obtain one explicit approval covering all three as ready for implementation
   and registration.
6. Do not register if either artifact is absent, either approval is missing, or
   the user cancels.
7. Ensure `.local/bin/ra-ticket` exists by building it from
   `tools/ra-ticket/` when absent.
8. Run this exact command shape from the repository root, with shell-safe
   arguments and the approved repository-relative paths:

```sh
.local/bin/ra-ticket add \
  --title "Approved feature title" \
  --summary "Approved implementation scope summary" \
  --spec "docs/superpowers/specs/2026-07-16-approved-feature-design.md" \
  --plan "docs/superpowers/plans/2026-07-16-approved-feature.md" \
  --json
```

9. Verify the returned ticket has status `ready`, then report its ID, title,
   design path, and plan path. On duplicate-plan output, run
   `.local/bin/ra-ticket list --json`, select the item whose `plan_path` exactly
   matches the approved repository-relative plan path, and report that existing
   ticket rather than modifying the database manually.

The quoted values above demonstrate argument shape; the skill must substitute
the actual jointly approved title, summary, and artifact paths from the current
run.

- [ ] **Step 3: Verify the validator detects ordering regressions**

Run:

```sh
.agents/skills/prepare-feature-ticket/scripts/validate-skill.sh
tmp_skill=$(mktemp)
awk '!/one explicit approval covering all/' .agents/skills/prepare-feature-ticket/SKILL.md > "$tmp_skill"
if .agents/skills/prepare-feature-ticket/scripts/validate-skill.sh "$tmp_skill"; then
  rm -f "$tmp_skill"
  exit 1
fi
rm -f "$tmp_skill"
```

Expected: the real skill prints `OK`; the mutated copy fails with the missing
joint plan and registration approval gate.

- [ ] **Step 4: Commit the preparation skill**

```sh
git add .agents/skills/prepare-feature-ticket
git commit -m "feat: add feature ticket preparation skill"
```

---

### Task 6: Run Integrated Verification and Review the Complete Tool

**Files:**
- Verify: `mise.toml`
- Verify: `.gitignore`
- Verify: `README.md`
- Verify: `tools/ra-ticket/**`
- Verify: `.agents/skills/prepare-feature-ticket/**`
- Verify: `docs/superpowers/specs/2026-07-16-feature-ticket-queue-design.md`

**Interfaces:**
- Consumes: all outputs from Tasks 1–5.
- Produces: evidence that the approved design, implementation, CLI behavior, and skill gates agree.

- [ ] **Step 1: Run all automated checks**

From `tools/ra-ticket/`:

```sh
mise exec -- go test ./... -race
mise exec -- go vet ./...
mise exec -- go build -o ../../.local/bin/ra-ticket ./cmd/ra-ticket
```

From the repository root:

```sh
.agents/skills/prepare-feature-ticket/scripts/validate-skill.sh
git diff --check
git status --short
```

Expected: Go tests, race detection, vet, build, skill validation, and diff
checks pass. `.local/` does not appear in `git status`. The only unrelated
working-tree entry remains the user's pre-existing
`frontend/src/modules/story-bible/ui/story-context-panel.tsx` modification.

- [ ] **Step 2: Run a disposable end-to-end CLI scenario**

Do not write this smoke test into the personal `.local/tickets.db`. Add or run
an integration test under `internal/cli/run_test.go` that creates a temporary
repository and performs this exact sequence through `cli.Run`:

```text
add first -> add second -> next == first/ready
start first -> next == second/ready
done first -> reopen first -> next == first/ready
cancel first -> next == second/ready
```

Run:

```sh
mise exec -- go test ./internal/cli -run TestEndToEndFIFOAndLifecycle -v
```

Expected: PASS with no writes outside the test temporary directory.

- [ ] **Step 3: Review implementation against the approved design**

Compare the diff with
`docs/superpowers/specs/2026-07-16-feature-ticket-queue-design.md` and record
that every acceptance criterion is covered. Confirm specifically that no
command claims work automatically, `next` is read-only, both document paths
are validated, no hard-delete command exists, and the skill cannot register
before both approvals.

- [ ] **Step 4: Request read-only implementation validation**

Use the available `impl-validator` skill or a read-only review agent with these
inputs: the approved design path, this plan, the complete implementation diff,
the CLI route `ra-ticket {add,list,next,show,start,done,cancel,reopen}`, and all
verification output. Accept or reject each finding with concrete evidence and
resolve every accepted finding before completion.

- [ ] **Step 5: Commit any verification-only test correction**

If Step 2 required adding the named end-to-end test, commit only that test:

```sh
git add tools/ra-ticket/internal/cli/run_test.go
git commit -m "test: verify feature ticket queue workflow"
```

If the test already exists from Task 4 and no file changed, do not create an
empty commit.
