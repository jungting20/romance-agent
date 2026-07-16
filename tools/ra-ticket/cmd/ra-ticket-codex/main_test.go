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
