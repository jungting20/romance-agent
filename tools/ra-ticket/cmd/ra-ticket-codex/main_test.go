package main

import (
	"strings"
	"testing"
)

func TestBuildPromptIncludesWorkerCompletionContract(t *testing.T) {
	ticket := claimedTicket{
		ID:       42,
		SpecPath: "docs/superpowers/specs/example-design.md",
		PlanPath: "docs/superpowers/plans/example.md",
	}

	prompt := buildPrompt(ticket)

	for _, required := range []string{
		ticket.SpecPath,
		ticket.PlanPath,
		"작업과 검증이 모두 성공한 경우에만",
		"앞부분: ZELLIJ_AGENT",
		"뒷부분: _WORKER_DONE",
		"티켓 식별자: ticket_id=42",
		"완료 전에는 연결된 결과를 출력하거나 언급하지 마세요.",
	} {
		if !strings.Contains(prompt, required) {
			t.Errorf("prompt missing %q:\n%s", required, prompt)
		}
	}
	if strings.Contains(prompt, workerCompletionMarker) {
		t.Errorf("prompt must not contain the assembled completion marker:\n%s", prompt)
	}
	if strings.Contains(prompt, "ticket_id=<실제 티켓 ID>") {
		t.Errorf("prompt must contain the actual ticket ID, not a placeholder:\n%s", prompt)
	}
}
