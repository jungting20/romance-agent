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
