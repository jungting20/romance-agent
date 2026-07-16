# ra-ticket-codex Worker Completion Marker Design

## Goal

Allow the Zellij worker controller to recognize when the Codex session launched
by `ra-ticket-codex` has genuinely completed its assigned feature work.

## Scope

Change only the implementation prompt constructed in
`tools/ra-ticket/cmd/ra-ticket-codex/main.go`. The prompt must instruct Codex to
print the exact marker below as the final standalone line of its final response
only after implementation, review, and verification finish successfully:

```text
ZELLIJ_AGENT_WORKER_DONE
```

Codex must not print the marker when work fails, is blocked, or remains
incomplete.

## Design

Append one explicit completion-marker instruction to the existing prompt
template. Keep the marker as literal prompt text because it has one use and no
runtime behavior of its own. The launcher continues to pass the approved spec
and plan paths to Codex and otherwise preserves its current process and ticket
lifecycle behavior.

The launcher itself must not emit the marker. Emitting from the parent process
would prove only that the Codex process exited, not that the assigned work was
successfully implemented, reviewed, and verified.

## Boundaries

This change does not alter ticket claiming, reopening, completion state,
process exit handling, persistence, frontend or backend behavior, APIs, or
domain contracts. It adds no dependencies and requires no UI plan, OpenAPI
change, or domain-document update.

## Acceptance Criteria

- The generated prompt contains the exact marker
  `ZELLIJ_AGENT_WORKER_DONE`.
- The prompt says to output the marker only after successful implementation,
  review, and verification.
- The prompt says the marker must be the final standalone line.
- The prompt says not to output it for failed, blocked, or incomplete work.
- Existing `ra-ticket` and `ra-ticket-codex` Go tests and builds succeed.

## Verification

Run from `tools/ra-ticket/`:

```sh
mise exec -- go test ./...
mise exec -- go build -o ../../.local/bin/ra-ticket ./cmd/ra-ticket
mise exec -- go build -o ../../.local/bin/ra-ticket-codex ./cmd/ra-ticket-codex
```

Review the focused diff and confirm the repository has no unrelated tracked
changes.
