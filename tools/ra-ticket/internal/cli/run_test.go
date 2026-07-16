package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"romance-agent/tools/ra-ticket/internal/ticket"
)

type harness struct {
	root   string
	stdout bytes.Buffer
	stderr bytes.Buffer
	deps   Dependencies
}

func newHarness(t *testing.T) *harness {
	t.Helper()
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, ".git"), 0o755); err != nil {
		t.Fatal(err)
	}
	return &harness{
		root: root,
		deps: Dependencies{
			StartDirectory: root,
			Now:            func() time.Time { return time.Date(2026, 7, 16, 12, 0, 0, 0, time.UTC) },
		},
	}
}

func (h *harness) run(t *testing.T, args ...string) int {
	t.Helper()
	h.stdout.Reset()
	h.stderr.Reset()
	return Run(context.Background(), args, &h.stdout, &h.stderr, h.deps)
}

func (h *harness) artifacts(t *testing.T, name string) (string, string) {
	t.Helper()
	spec := filepath.Join(h.root, "docs", "superpowers", "specs", name+"-design.md")
	plan := filepath.Join(h.root, "docs", "superpowers", "plans", name+".md")
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

func (h *harness) addJSON(t *testing.T, title, summary, spec, plan string) ticket.Ticket {
	t.Helper()
	if got := h.run(t, "add", "--title", title, "--summary", summary, "--spec", spec, "--plan", plan, "--json"); got != ExitOK {
		t.Fatalf("add exit = %d, stderr = %s", got, h.stderr.String())
	}
	return decodeTicket(t, h.stdout.Bytes())
}

func decodeTicket(t *testing.T, data []byte) ticket.Ticket {
	t.Helper()
	var got ticket.Ticket
	if err := json.Unmarshal(data, &got); err != nil {
		t.Fatalf("decode ticket JSON %q: %v", data, err)
	}
	return got
}

func TestAddJSONRegistersReadyTicketFromNestedDirectory(t *testing.T) {
	h := newHarness(t)
	spec, plan := h.artifacts(t, "search")
	nested := filepath.Join(h.root, "tools", "ra-ticket", "cmd")
	if err := os.MkdirAll(nested, 0o755); err != nil {
		t.Fatal(err)
	}
	h.deps.StartDirectory = nested

	got := h.addJSON(t, "Search", "Search story bible", spec, plan)
	if got.ID != 1 || got.Status != ticket.StatusReady {
		t.Fatalf("add ticket = %#v", got)
	}
	if got.SpecPath != "docs/superpowers/specs/search-design.md" || got.PlanPath != "docs/superpowers/plans/search.md" {
		t.Fatalf("add paths = %q, %q", got.SpecPath, got.PlanPath)
	}
}

func TestNextJSONReturnsReadyTicketWithoutMutation(t *testing.T) {
	h := newHarness(t)
	spec, plan := h.artifacts(t, "first")
	created := h.addJSON(t, "First", "First ticket", spec, plan)
	spec, plan = h.artifacts(t, "second")
	h.addJSON(t, "Second", "Second ticket", spec, plan)

	if got := h.run(t, "next", "--json"); got != ExitOK {
		t.Fatalf("next exit = %d, stderr = %s", got, h.stderr.String())
	}
	next := decodeTicket(t, h.stdout.Bytes())
	if next.ID != created.ID || next.Status != ticket.StatusReady {
		t.Fatalf("next ticket = %#v", next)
	}

	if got := h.run(t, "show", "1", "--json"); got != ExitOK {
		t.Fatalf("show exit = %d, stderr = %s", got, h.stderr.String())
	}
	shown := decodeTicket(t, h.stdout.Bytes())
	if shown.Status != ticket.StatusReady || !shown.UpdatedAt.Equal(created.UpdatedAt) {
		t.Fatalf("next mutated ticket: created=%#v shown=%#v", created, shown)
	}
}

func TestEndToEndFIFOAndLifecycle(t *testing.T) {
	h := newHarness(t)
	firstSpec, firstPlan := h.artifacts(t, "first")
	first := h.addJSON(t, "First", "First ticket", firstSpec, firstPlan)
	secondSpec, secondPlan := h.artifacts(t, "second")
	second := h.addJSON(t, "Second", "Second ticket", secondSpec, secondPlan)

	assertNext := func(wantID int64, wantStatus ticket.Status) {
		t.Helper()
		if got := h.run(t, "next", "--json"); got != ExitOK {
			t.Fatalf("next exit = %d, stderr = %s", got, h.stderr.String())
		}
		next := decodeTicket(t, h.stdout.Bytes())
		if next.ID != wantID || next.Status != wantStatus {
			t.Fatalf("next ticket = %#v, want ID %d/status %q", next, wantID, wantStatus)
		}
	}

	assertNext(first.ID, ticket.StatusReady)

	firstID := strconv.FormatInt(first.ID, 10)
	if got := h.run(t, "start", firstID, "--json"); got != ExitOK {
		t.Fatalf("start exit = %d, stderr = %s", got, h.stderr.String())
	}
	if started := decodeTicket(t, h.stdout.Bytes()); started.ID != first.ID || started.Status != ticket.StatusInProgress {
		t.Fatalf("started ticket = %#v, want ID %d/status %q", started, first.ID, ticket.StatusInProgress)
	}
	assertNext(second.ID, ticket.StatusReady)

	if got := h.run(t, "done", firstID, "--json"); got != ExitOK {
		t.Fatalf("done exit = %d, stderr = %s", got, h.stderr.String())
	}
	if done := decodeTicket(t, h.stdout.Bytes()); done.ID != first.ID || done.Status != ticket.StatusDone {
		t.Fatalf("done ticket = %#v, want ID %d/status %q", done, first.ID, ticket.StatusDone)
	}
	if got := h.run(t, "reopen", firstID, "--json"); got != ExitOK {
		t.Fatalf("reopen exit = %d, stderr = %s", got, h.stderr.String())
	}
	if reopened := decodeTicket(t, h.stdout.Bytes()); reopened.ID != first.ID || reopened.Status != ticket.StatusReady {
		t.Fatalf("reopened ticket = %#v, want ID %d/status %q", reopened, first.ID, ticket.StatusReady)
	}
	assertNext(first.ID, ticket.StatusReady)

	if got := h.run(t, "cancel", firstID, "--json"); got != ExitOK {
		t.Fatalf("cancel exit = %d, stderr = %s", got, h.stderr.String())
	}
	if cancelled := decodeTicket(t, h.stdout.Bytes()); cancelled.ID != first.ID || cancelled.Status != ticket.StatusCancelled {
		t.Fatalf("cancelled ticket = %#v, want ID %d/status %q", cancelled, first.ID, ticket.StatusCancelled)
	}
	assertNext(second.ID, ticket.StatusReady)
}

func TestNextJSONReportsEmptyQueue(t *testing.T) {
	h := newHarness(t)

	if got := h.run(t, "next", "--json"); got != ExitEmptyQueue {
		t.Fatalf("next exit = %d, want %d", got, ExitEmptyQueue)
	}
	if got, want := h.stderr.String(), "{\"error\":\"no ready tickets\",\"code\":\"empty_queue\"}\n"; got != want {
		t.Fatalf("stderr = %q, want %q", got, want)
	}
}

func TestListJSONFiltersReadyTickets(t *testing.T) {
	h := newHarness(t)
	firstSpec, firstPlan := h.artifacts(t, "first")
	first := h.addJSON(t, "First", "First ticket", firstSpec, firstPlan)
	secondSpec, secondPlan := h.artifacts(t, "second")
	second := h.addJSON(t, "Second", "Second ticket", secondSpec, secondPlan)
	if got := h.run(t, "start", "2", "--json"); got != ExitOK {
		t.Fatalf("start exit = %d, stderr = %s", got, h.stderr.String())
	}

	if got := h.run(t, "list", "--status", "ready", "--json"); got != ExitOK {
		t.Fatalf("list exit = %d, stderr = %s", got, h.stderr.String())
	}
	var tickets []ticket.Ticket
	if err := json.Unmarshal(h.stdout.Bytes(), &tickets); err != nil {
		t.Fatalf("decode list JSON %q: %v", h.stdout.Bytes(), err)
	}
	if len(tickets) != 1 || tickets[0].ID != first.ID || tickets[0].ID == second.ID {
		t.Fatalf("ready tickets = %#v", tickets)
	}
}

func TestLifecycleCommandsApplyTransitions(t *testing.T) {
	tests := []struct {
		name    string
		actions []string
		status  ticket.Status
	}{
		{name: "start", actions: []string{"start"}, status: ticket.StatusInProgress},
		{name: "start then done", actions: []string{"start", "done"}, status: ticket.StatusDone},
		{name: "cancel", actions: []string{"cancel"}, status: ticket.StatusCancelled},
		{name: "cancel then reopen", actions: []string{"cancel", "reopen"}, status: ticket.StatusReady},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			h := newHarness(t)
			spec, plan := h.artifacts(t, "flow")
			created := h.addJSON(t, "Flow", "Lifecycle ticket", spec, plan)
			for _, action := range tt.actions {
				if got := h.run(t, action, "1", "--json"); got != ExitOK {
					t.Fatalf("%s exit = %d, stderr = %s", action, got, h.stderr.String())
				}
				created = decodeTicket(t, h.stdout.Bytes())
			}
			if created.Status != tt.status {
				t.Fatalf("status = %q, want %q", created.Status, tt.status)
			}
		})
	}
}

func TestHumanOutputContract(t *testing.T) {
	h := newHarness(t)
	if got := h.run(t, "list"); got != ExitOK {
		t.Fatalf("empty list exit = %d, stderr = %s", got, h.stderr.String())
	}
	if got, want := h.stdout.String(), "No tickets.\n"; got != want {
		t.Fatalf("empty list = %q, want %q", got, want)
	}

	spec, plan := h.artifacts(t, "human")
	created := h.addJSON(t, "Human title", "Human summary", spec, plan)
	if got := h.run(t, "show", "1"); got != ExitOK {
		t.Fatalf("show exit = %d, stderr = %s", got, h.stderr.String())
	}
	for _, value := range []string{"ID: 1", "Status: ready", "Title: Human title", "Summary: Human summary", "Spec: " + created.SpecPath, "Plan: " + created.PlanPath} {
		if !strings.Contains(h.stdout.String(), value) {
			t.Fatalf("show output %q does not contain %q", h.stdout.String(), value)
		}
	}

	if got := h.run(t, "list"); got != ExitOK {
		t.Fatalf("list exit = %d, stderr = %s", got, h.stderr.String())
	}
	if got, want := h.stdout.String(), "1\tready\tHuman title\tdocs/superpowers/plans/human.md\n"; got != want {
		t.Fatalf("list output = %q, want %q", got, want)
	}
}

func TestUsageErrors(t *testing.T) {
	tests := [][]string{
		{"show", "not-an-id"},
		{"start", "0"},
		{"done", "1", "extra"},
		{"add", "--title", "only title"},
		{"list", "--status", "ready", "extra"},
		{"unknown"},
	}

	for _, args := range tests {
		t.Run(strings.Join(args, " "), func(t *testing.T) {
			h := newHarness(t)
			if got := h.run(t, args...); got != ExitUsage {
				t.Fatalf("Run(%q) = %d, want %d; stderr = %s", args, got, ExitUsage, h.stderr.String())
			}
		})
	}
}

func TestNotFoundAndDomainErrorsMapToExitCodes(t *testing.T) {
	t.Run("missing ticket", func(t *testing.T) {
		h := newHarness(t)
		if got := h.run(t, "show", "1", "--json"); got != ExitNotFound {
			t.Fatalf("show exit = %d, want %d; stderr = %s", got, ExitNotFound, h.stderr.String())
		}
	})

	t.Run("duplicate plan", func(t *testing.T) {
		h := newHarness(t)
		spec, plan := h.artifacts(t, "duplicate")
		h.addJSON(t, "First", "First ticket", spec, plan)
		if got := h.run(t, "add", "--title", "Second", "--summary", "Second ticket", "--spec", spec, "--plan", plan); got != ExitDuplicate {
			t.Fatalf("duplicate exit = %d, want %d; stderr = %s", got, ExitDuplicate, h.stderr.String())
		}
	})

	t.Run("invalid transition", func(t *testing.T) {
		h := newHarness(t)
		spec, plan := h.artifacts(t, "invalid-transition")
		h.addJSON(t, "Ready", "Ready ticket", spec, plan)
		if got := h.run(t, "done", "1"); got != ExitInvalidTransition {
			t.Fatalf("done exit = %d, want %d; stderr = %s", got, ExitInvalidTransition, h.stderr.String())
		}
	})

	t.Run("missing artifact", func(t *testing.T) {
		h := newHarness(t)
		_, plan := h.artifacts(t, "existing")
		missingSpec := filepath.Join(h.root, "docs", "superpowers", "specs", "missing-design.md")
		if got := h.run(t, "add", "--title", "Missing", "--summary", "Missing artifact", "--spec", missingSpec, "--plan", plan); got != ExitValidation {
			t.Fatalf("missing artifact exit = %d, want %d; stderr = %s", got, ExitValidation, h.stderr.String())
		}
	})

	t.Run("misplaced artifact", func(t *testing.T) {
		h := newHarness(t)
		spec, _ := h.artifacts(t, "misplaced")
		misplacedPlan := filepath.Join(h.root, "docs", "plans", "misplaced.md")
		if err := os.MkdirAll(filepath.Dir(misplacedPlan), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(misplacedPlan, []byte("# Wrong place\n"), 0o644); err != nil {
			t.Fatal(err)
		}
		if got := h.run(t, "add", "--title", "Misplaced", "--summary", "Misplaced plan", "--spec", spec, "--plan", misplacedPlan); got != ExitValidation {
			t.Fatalf("misplaced artifact exit = %d, want %d; stderr = %s", got, ExitValidation, h.stderr.String())
		}
	})
}
