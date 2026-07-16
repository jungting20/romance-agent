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
