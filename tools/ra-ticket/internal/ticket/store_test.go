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
		Title:    "Search story bible",
		Summary:  "Add indexed story-bible search.",
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

func TestOpenInitializesSchemaIdempotently(t *testing.T) {
	store, root := newTestStore(t)
	databasePath := filepath.Join(root, ".local", "tickets.db")
	if err := store.Close(); err != nil {
		t.Fatal(err)
	}

	second, err := Open(context.Background(), root, databasePath, func() time.Time { return fixedNow })
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = second.Close() })

	spec, plan := writeArtifacts(t, root, "idempotent")
	if _, err := second.Add(context.Background(), CreateInput{
		Title:    "Idempotent schema",
		Summary:  "Open an initialized ticket database.",
		SpecPath: spec,
		PlanPath: plan,
	}); err != nil {
		t.Fatal(err)
	}
}

func TestAddAcceptsRepositoryRelativeArtifactPaths(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "relative")
	relativeSpec, err := filepath.Rel(root, spec)
	if err != nil {
		t.Fatal(err)
	}
	relativePlan, err := filepath.Rel(root, plan)
	if err != nil {
		t.Fatal(err)
	}

	got, err := store.Add(context.Background(), CreateInput{
		Title:    "Relative artifacts",
		Summary:  "Register repository-relative artifact paths.",
		SpecPath: relativeSpec,
		PlanPath: relativePlan,
	})
	if err != nil {
		t.Fatal(err)
	}
	if got.SpecPath != "docs/superpowers/specs/relative-design.md" || got.PlanPath != "docs/superpowers/plans/relative.md" {
		t.Fatalf("stored paths = %q, %q", got.SpecPath, got.PlanPath)
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
	symlink := filepath.Join(root, "docs", "superpowers", "plans", "outside.md")
	if err := os.Symlink(outside, symlink); err != nil {
		t.Fatal(err)
	}

	cases := []CreateInput{
		{Title: "", Summary: "summary", SpecPath: spec, PlanPath: plan},
		{Title: "title", Summary: "", SpecPath: spec, PlanPath: plan},
		{Title: "title", Summary: "summary", SpecPath: filepath.Join(root, "missing.md"), PlanPath: plan},
		{Title: "title", Summary: "summary", SpecPath: spec, PlanPath: outside},
		{Title: "title", Summary: "summary", SpecPath: spec, PlanPath: symlink},
	}
	for _, input := range cases {
		if _, err := store.Add(context.Background(), input); !errors.Is(err, ErrInvalidArtifact) {
			t.Fatalf("Add(%#v) error = %v, want ErrInvalidArtifact", input, err)
		}
	}
}

func TestGetReturnsTicketAndRejectsUnknownID(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "get")
	created, err := store.Add(context.Background(), CreateInput{
		Title:    "Get ticket",
		Summary:  "Retrieve one ticket.",
		SpecPath: spec,
		PlanPath: plan,
	})
	if err != nil {
		t.Fatal(err)
	}

	got, err := store.Get(context.Background(), created.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got != created {
		t.Fatalf("Get() = %#v, want %#v", got, created)
	}
	if _, err := store.Get(context.Background(), created.ID+1); !errors.Is(err, ErrNotFound) {
		t.Fatalf("Get() error = %v, want ErrNotFound", err)
	}
}

func TestListFiltersStatusesAndOrdersFIFOTiesByID(t *testing.T) {
	store, root := newTestStore(t)
	firstSpec, firstPlan := writeArtifacts(t, root, "first")
	first, err := store.Add(context.Background(), CreateInput{Title: "First", Summary: "First summary", SpecPath: firstSpec, PlanPath: firstPlan})
	if err != nil {
		t.Fatal(err)
	}
	secondSpec, secondPlan := writeArtifacts(t, root, "second")
	second, err := store.Add(context.Background(), CreateInput{Title: "Second", Summary: "Second summary", SpecPath: secondSpec, PlanPath: secondPlan})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Transition(context.Background(), second.ID, ActionStart); err != nil {
		t.Fatal(err)
	}

	all, err := store.List(context.Background(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(all) != 2 || all[0].ID != first.ID || all[1].ID != second.ID {
		t.Fatalf("List(nil) = %#v", all)
	}

	ready, err := store.List(context.Background(), statusPtr(StatusReady))
	if err != nil {
		t.Fatal(err)
	}
	if len(ready) != 1 || ready[0].ID != first.ID {
		t.Fatalf("List(ready) = %#v", ready)
	}

	inProgress, err := store.List(context.Background(), statusPtr(StatusInProgress))
	if err != nil {
		t.Fatal(err)
	}
	if len(inProgress) != 1 || inProgress[0].ID != second.ID {
		t.Fatalf("List(in_progress) = %#v", inProgress)
	}

	invalid := Status("unknown")
	if _, err := store.List(context.Background(), &invalid); !errors.Is(err, ErrInvalidTransition) {
		t.Fatalf("List(unknown) error = %v, want ErrInvalidTransition", err)
	}
}

func TestListReturnsAllocatedEmptySlice(t *testing.T) {
	store, _ := newTestStore(t)

	got, err := store.List(context.Background(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if got == nil || len(got) != 0 {
		t.Fatalf("List(nil) = %#v, want allocated empty slice", got)
	}
}

func TestNextReturnsOldestReadyWithoutMutation(t *testing.T) {
	store, root := newTestStore(t)
	spec1, plan1 := writeArtifacts(t, root, "first")
	first, err := store.Add(context.Background(), CreateInput{Title: "First", Summary: "First summary", SpecPath: spec1, PlanPath: plan1})
	if err != nil {
		t.Fatal(err)
	}
	spec2, plan2 := writeArtifacts(t, root, "second")
	if _, err := store.Add(context.Background(), CreateInput{Title: "Second", Summary: "Second summary", SpecPath: spec2, PlanPath: plan2}); err != nil {
		t.Fatal(err)
	}

	got, err := store.Next(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if got.ID != first.ID || got.Status != StatusReady {
		t.Fatalf("Next() = %#v", got)
	}
	after, err := store.Get(context.Background(), first.ID)
	if err != nil {
		t.Fatal(err)
	}
	if after.Status != first.Status || !after.UpdatedAt.Equal(first.UpdatedAt) || after.StartedAt != nil {
		t.Fatalf("Next mutated ticket: before=%#v after=%#v", first, after)
	}
}

func TestNextReturnsEmptyQueueAfterReadyTicketsLeaveQueue(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "first")
	created, err := store.Add(context.Background(), CreateInput{Title: "First", Summary: "First summary", SpecPath: spec, PlanPath: plan})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Transition(context.Background(), created.ID, ActionStart); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Next(context.Background()); !errors.Is(err, ErrEmptyQueue) {
		t.Fatalf("Next() error = %v, want ErrEmptyQueue", err)
	}
}

func TestLifecycleTransitionsAndTimestamps(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "flow")
	created, err := store.Add(context.Background(), CreateInput{Title: "Flow", Summary: "Flow summary", SpecPath: spec, PlanPath: plan})
	if err != nil {
		t.Fatal(err)
	}

	started, err := store.Transition(context.Background(), created.ID, ActionStart)
	if err != nil {
		t.Fatal(err)
	}
	if started.Status != StatusInProgress || started.StartedAt == nil || !started.StartedAt.Equal(fixedNow) || !started.UpdatedAt.Equal(fixedNow) {
		t.Fatalf("start = %#v", started)
	}

	done, err := store.Transition(context.Background(), created.ID, ActionDone)
	if err != nil {
		t.Fatal(err)
	}
	if done.Status != StatusDone || done.CompletedAt == nil || !done.CompletedAt.Equal(fixedNow) || !done.UpdatedAt.Equal(fixedNow) {
		t.Fatalf("done = %#v", done)
	}

	reopened, err := store.Transition(context.Background(), created.ID, ActionReopen)
	if err != nil {
		t.Fatal(err)
	}
	if reopened.Status != StatusReady || reopened.StartedAt != nil || reopened.CompletedAt != nil || reopened.CancelledAt != nil || !reopened.UpdatedAt.Equal(fixedNow) {
		t.Fatalf("reopen = %#v", reopened)
	}
}

func TestLifecycleAllowsCancellationAndReopening(t *testing.T) {
	cases := []struct {
		name    string
		actions []Action
		status  Status
	}{
		{name: "ready to cancelled", actions: []Action{ActionCancel}, status: StatusCancelled},
		{name: "in progress to cancelled", actions: []Action{ActionStart, ActionCancel}, status: StatusCancelled},
		{name: "cancelled to ready", actions: []Action{ActionCancel, ActionReopen}, status: StatusReady},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			store, root := newTestStore(t)
			spec, plan := writeArtifacts(t, root, "flow")
			created, err := store.Add(context.Background(), CreateInput{Title: "Flow", Summary: "Flow summary", SpecPath: spec, PlanPath: plan})
			if err != nil {
				t.Fatal(err)
			}

			var got Ticket
			for _, action := range tc.actions {
				got, err = store.Transition(context.Background(), created.ID, action)
				if err != nil {
					t.Fatal(err)
				}
			}
			if got.Status != tc.status {
				t.Fatalf("Transition() status = %q, want %q", got.Status, tc.status)
			}
			if tc.status == StatusCancelled && (got.CancelledAt == nil || !got.CancelledAt.Equal(fixedNow)) {
				t.Fatalf("cancelled ticket = %#v", got)
			}
			if tc.status == StatusReady && (got.StartedAt != nil || got.CompletedAt != nil || got.CancelledAt != nil) {
				t.Fatalf("reopened ticket = %#v", got)
			}
		})
	}
}

func TestInvalidTransitionDoesNotMutateTicket(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "flow")
	created, err := store.Add(context.Background(), CreateInput{Title: "Flow", Summary: "Flow summary", SpecPath: spec, PlanPath: plan})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Transition(context.Background(), created.ID, ActionDone); !errors.Is(err, ErrInvalidTransition) {
		t.Fatalf("Transition() error = %v, want ErrInvalidTransition", err)
	}
	after, err := store.Get(context.Background(), created.ID)
	if err != nil {
		t.Fatal(err)
	}
	if after.Status != StatusReady || !after.UpdatedAt.Equal(created.UpdatedAt) {
		t.Fatalf("invalid transition mutated ticket: %#v", after)
	}
}

func TestTransitionRejectsUnknownIDsAndActions(t *testing.T) {
	store, root := newTestStore(t)
	spec, plan := writeArtifacts(t, root, "flow")
	created, err := store.Add(context.Background(), CreateInput{Title: "Flow", Summary: "Flow summary", SpecPath: spec, PlanPath: plan})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := store.Transition(context.Background(), created.ID+1, ActionStart); !errors.Is(err, ErrNotFound) {
		t.Fatalf("Transition(unknown ID) error = %v, want ErrNotFound", err)
	}
	if _, err := store.Transition(context.Background(), created.ID, Action("unknown")); !errors.Is(err, ErrInvalidTransition) {
		t.Fatalf("Transition(unknown action) error = %v, want ErrInvalidTransition", err)
	}
	after, err := store.Get(context.Background(), created.ID)
	if err != nil {
		t.Fatal(err)
	}
	if after != created {
		t.Fatalf("unknown action mutated ticket: before=%#v after=%#v", created, after)
	}
}

func statusPtr(status Status) *Status { return &status }
