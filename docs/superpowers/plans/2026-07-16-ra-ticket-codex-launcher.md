# RA Ticket Codex Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small Go command that claims the next ready local ticket and opens interactive Codex with its approved artifact paths in the initial feature-development prompt.

**Architecture:** Add one command to the existing `tools/ra-ticket` Go module. It delegates ticket selection and lifecycle mutation to the existing ignored `ra-ticket` binary, parses its JSON response, and starts `codex` with inherited terminal streams; only a child-process start failure reopens the claimed ticket.

**Tech Stack:** Go standard library, existing `tools/ra-ticket/internal/repository` package, existing `ra-ticket` CLI, Codex CLI.

## Global Constraints

- Create only `tools/ra-ticket/cmd/ra-ticket-codex/main.go` for implementation.
- Do not change ticket storage, lifecycle semantics, application code, or the feature-development skill.
- Do not add or run tests.
- Verify only by formatting and compiling the new command.
- Preserve unrelated working-tree changes.

---

### Task 1: Implement the interactive ticket launcher

**Files:**
- Create: `tools/ra-ticket/cmd/ra-ticket-codex/main.go`

**Interfaces:**
- Consumes: `.local/bin/ra-ticket next --json`, `.local/bin/ra-ticket reopen ID`, `repository.FindRoot(string)`, and `codex -C ROOT PROMPT`.
- Produces: `.local/bin/ra-ticket-codex`, an interactive launcher with process exit status `0` only when the Codex child exits successfully.

- [ ] **Step 1: Create the launcher command**

Create `tools/ra-ticket/cmd/ra-ticket-codex/main.go` with:

```go
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"romance-agent/tools/ra-ticket/internal/repository"
)

type claimedTicket struct {
	ID       int64  `json:"id"`
	SpecPath string `json:"spec_path"`
	PlanPath string `json:"plan_path"`
}

func main() {
	if err := run(); err != nil {
		_, _ = fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run() error {
	workingDirectory, err := os.Getwd()
	if err != nil {
		return fmt.Errorf("get working directory: %w", err)
	}
	root, err := repository.FindRoot(workingDirectory)
	if err != nil {
		return err
	}

	ticketBinary := filepath.Join(root, ".local", "bin", "ra-ticket")
	ticket, err := claimNext(ticketBinary, root)
	if err != nil {
		return err
	}

	prompt := fmt.Sprintf(`$feature-development

다음 승인된 문서를 authoritative implementation input으로 사용해 기능을 구현해줘.

- 설계: %s
- 구현 계획: %s

brainstorming과 writing-plans는 다시 수행하지 말고,
feature-development의 전체 구현·검토·검증 절차를 따라줘.
티켓에 없는 범위를 추측해서 추가하지 마.`, ticket.SpecPath, ticket.PlanPath)

	codex := exec.Command("codex", "-C", root, prompt)
	codex.Stdin = os.Stdin
	codex.Stdout = os.Stdout
	codex.Stderr = os.Stderr
	if err := codex.Start(); err != nil {
		if reopenErr := reopen(ticketBinary, root, ticket.ID); reopenErr != nil {
			return fmt.Errorf("start codex: %v; reopen ticket %d: %w", err, ticket.ID, reopenErr)
		}
		return fmt.Errorf("start codex: %w; ticket %d returned to ready", err, ticket.ID)
	}
	if err := codex.Wait(); err != nil {
		return fmt.Errorf("codex exited: %w", err)
	}
	return nil
}

func claimNext(ticketBinary, root string) (claimedTicket, error) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	command := exec.Command(ticketBinary, "next", "--json")
	command.Dir = root
	command.Stdout = &stdout
	command.Stderr = &stderr
	if err := command.Run(); err != nil {
		message := strings.TrimSpace(stderr.String())
		if message == "" {
			message = err.Error()
		}
		return claimedTicket{}, fmt.Errorf("claim next ticket: %s", message)
	}

	var ticket claimedTicket
	if err := json.Unmarshal(stdout.Bytes(), &ticket); err != nil {
		return claimedTicket{}, fmt.Errorf("decode claimed ticket: %w", err)
	}
	if ticket.ID <= 0 || ticket.SpecPath == "" || ticket.PlanPath == "" {
		return claimedTicket{}, fmt.Errorf("decode claimed ticket: required fields are missing")
	}
	return ticket, nil
}

func reopen(ticketBinary, root string, id int64) error {
	command := exec.Command(ticketBinary, "reopen", strconv.FormatInt(id, 10), "--json")
	command.Dir = root
	output, err := command.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s: %w", strings.TrimSpace(string(output)), err)
	}
	return nil
}
```

- [ ] **Step 2: Format the command**

Run from `tools/ra-ticket/`:

```sh
mise exec -- gofmt -w cmd/ra-ticket-codex/main.go
```

Expected: exit status `0` with no output.

- [ ] **Step 3: Compile the ignored local binary**

Run from `tools/ra-ticket/`:

```sh
mise exec -- go build -o ../../.local/bin/ra-ticket-codex ./cmd/ra-ticket-codex
```

Expected: exit status `0` and `.local/bin/ra-ticket-codex` exists.

- [ ] **Step 4: Review and commit the implementation**

```sh
git diff --check -- tools/ra-ticket/cmd/ra-ticket-codex/main.go
git diff -- tools/ra-ticket/cmd/ra-ticket-codex/main.go
git add -- tools/ra-ticket/cmd/ra-ticket-codex/main.go
git commit -m "feat: launch Codex from next ticket"
```

Expected: one implementation commit containing only the new command source.
