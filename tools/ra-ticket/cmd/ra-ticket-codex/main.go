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
