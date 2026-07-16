# ra-ticket-codex Worker Completion Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Codex session launched by `ra-ticket-codex` print `ZELLIJ_AGENT_WORKER_DONE` as its final standalone line only after successful implementation, review, and verification.

**Architecture:** Extract the existing prompt construction into a small pure function that accepts the claimed ticket and returns the prompt. Extend that prompt with the exact completion-marker contract and unit-test the generated text without starting child processes.

**Tech Stack:** Go 1.26, Go standard library, existing `tools/ra-ticket` module.

## Global Constraints

- The exact marker is `ZELLIJ_AGENT_WORKER_DONE`.
- The marker is emitted only after implementation, review, and verification finish successfully.
- The marker is the final standalone line of the final response.
- Failed, blocked, or incomplete work must not emit the marker.
- The launcher itself must not print the marker.
- Do not change ticket lifecycle, persistence, APIs, UI, backend, or domain contracts.
- Add no dependencies.

---

### Task 1: Add the worker completion contract to the Codex prompt

**Files:**
- Modify: `tools/ra-ticket/cmd/ra-ticket-codex/main.go`
- Create: `tools/ra-ticket/cmd/ra-ticket-codex/main_test.go`

**Interfaces:**
- Consumes: existing `claimedTicket` values with `SpecPath` and `PlanPath`.
- Produces: `buildPrompt(ticket claimedTicket) string`, used by `run` as the complete Codex prompt.

- [ ] **Step 1: Write the failing prompt-contract test**

Create `tools/ra-ticket/cmd/ra-ticket-codex/main_test.go`:

```go
package main

import (
	"strings"
	"testing"
)

func TestBuildPromptIncludesWorkerCompletionContract(t *testing.T) {
	ticket := claimedTicket{
		SpecPath: "docs/superpowers/specs/example-design.md",
		PlanPath: "docs/superpowers/plans/example.md",
	}

	prompt := buildPrompt(ticket)

	for _, required := range []string{
		ticket.SpecPath,
		ticket.PlanPath,
		"구현·검토·검증을 모두 성공적으로 완료한 경우에만",
		"실패, 차단 또는 미완료 상태에서는 이 마커를 출력하지 마.",
	} {
		if !strings.Contains(prompt, required) {
			t.Errorf("prompt missing %q:\n%s", required, prompt)
		}
	}
	if !strings.HasSuffix(prompt, "\nZELLIJ_AGENT_WORKER_DONE") {
		t.Errorf("prompt must end with standalone completion marker:\n%s", prompt)
	}
}
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run from `tools/ra-ticket/`:

```sh
mise exec -- go test ./cmd/ra-ticket-codex -run TestBuildPromptIncludesWorkerCompletionContract -v
```

Expected: compilation fails because `buildPrompt` is undefined.

- [ ] **Step 3: Extract prompt construction and add the marker contract**

In `tools/ra-ticket/cmd/ra-ticket-codex/main.go`, replace the inline
`fmt.Sprintf` assignment in `run` with:

```go
	prompt := buildPrompt(ticket)
```

Add this function below `run`:

```go
func buildPrompt(ticket claimedTicket) string {
	return fmt.Sprintf(`$feature-development

다음 승인된 문서를 authoritative implementation input으로 사용해 기능을 구현해줘.

- 설계: %s
- 구현 계획: %s

brainstorming과 writing-plans는 다시 수행하지 말고,
feature-development의 전체 구현·검토·검증 절차를 따라줘.
티켓에 없는 범위를 추측해서 추가하지 마.

구현·검토·검증을 모두 성공적으로 완료한 경우에만 최종 응답의 마지막 줄에
아래 종료 마커를 다른 문자 없이 단독으로 출력해.
실패, 차단 또는 미완료 상태에서는 이 마커를 출력하지 마.
ZELLIJ_AGENT_WORKER_DONE`, ticket.SpecPath, ticket.PlanPath)
}
```

Do not add any launcher-side `fmt.Println` call for the marker.

- [ ] **Step 4: Format and rerun the focused test**

Run from `tools/ra-ticket/`:

```sh
mise exec -- gofmt -w cmd/ra-ticket-codex/main.go cmd/ra-ticket-codex/main_test.go
mise exec -- go test ./cmd/ra-ticket-codex -run TestBuildPromptIncludesWorkerCompletionContract -v
```

Expected: `TestBuildPromptIncludesWorkerCompletionContract` passes.

- [ ] **Step 5: Run full module tests and build both commands**

Run from `tools/ra-ticket/`:

```sh
mise exec -- go test ./...
mise exec -- go build -o ../../.local/bin/ra-ticket ./cmd/ra-ticket
mise exec -- go build -o ../../.local/bin/ra-ticket-codex ./cmd/ra-ticket-codex
```

Expected: every command exits with status 0. The two ignored local binaries are
updated without tracked source changes outside this task.

- [ ] **Step 6: Review and commit the implementation**

Run from the repository root:

```sh
git diff --check
git diff -- tools/ra-ticket/cmd/ra-ticket-codex/main.go tools/ra-ticket/cmd/ra-ticket-codex/main_test.go
git status --short
git add tools/ra-ticket/cmd/ra-ticket-codex/main.go tools/ra-ticket/cmd/ra-ticket-codex/main_test.go
git commit -m "feat: signal completed ticket workers"
```

Expected: the focused diff contains only the prompt extraction, completion
contract, and its unit test before the commit succeeds.
