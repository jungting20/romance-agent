# RA Ticket Codex Launcher Design

## Goal

Add a small Go launcher that atomically claims the next ready local feature
ticket and starts an interactive Codex CLI session with the ticket's approved
design and implementation-plan paths in the initial prompt.

## Command and Location

The launcher source lives at
`tools/ra-ticket/cmd/ra-ticket-codex/main.go` and builds to the ignored local
binary `.local/bin/ra-ticket-codex`.

The launcher may be invoked from any directory inside the repository. It finds
the repository root using the existing repository discovery package.

## Execution Flow

1. Run `<repository-root>/.local/bin/ra-ticket next --json` from the repository
   root.
2. Stop and forward a useful error when the ticket command fails or its JSON
   output is invalid.
3. Read `id`, `spec_path`, and `plan_path` from the claimed ticket.
4. Construct the approved initial prompt shown below.
5. Start `codex -C <repository-root> <prompt>` with the launcher's standard
   input, output, and error streams attached, preserving an interactive Codex
   session.
6. If the Codex child process cannot be started, run
   `.local/bin/ra-ticket reopen <id>` to return the claimed ticket to `ready`.
7. Once the Codex child process has successfully started, leave the ticket
   `in_progress` regardless of how that interactive process later exits.

The launcher does not mark tickets `done`; implementation completion remains a
separate explicit lifecycle decision.

## Initial Prompt

The complete prompt passed as one Codex argument is:

```text
$feature-development

다음 승인된 문서를 authoritative implementation input으로 사용해 기능을 구현해줘.

- 설계: <spec_path>
- 구현 계획: <plan_path>

brainstorming과 writing-plans는 다시 수행하지 말고,
feature-development의 전체 구현·검토·검증 절차를 따라줘.
티켓에 없는 범위를 추측해서 추가하지 마.
```

Only `<spec_path>` and `<plan_path>` are substituted from the claimed ticket.
The ticket ID, title, and summary are not included in the prompt.

## Error Handling

- Missing `ra-ticket`, an empty queue, ticket-command failures, and malformed
  ticket JSON stop before Codex is started.
- A failure to locate or start `codex` attempts to reopen the ticket. If reopen
  also fails, the launcher reports both failures and exits unsuccessfully.
- A non-zero exit after Codex has started is returned to the caller without
  reopening the ticket, because it may represent an intentional interruption
  of an active implementation session.

## Scope and Verification

This change adds only the Go launcher command. It does not change the ticket
schema, ticket state machine, existing `ra-ticket` commands, feature-development
skill, or application code.

Per the requested lightweight workflow, no tests are added or run. Verification
is limited to formatting and compiling the new command.
