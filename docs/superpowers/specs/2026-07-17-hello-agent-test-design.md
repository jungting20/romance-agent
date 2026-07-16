# Hello Agent Test

## Goal

Verify that `ra-ticket-codex` can launch a coding agent and that the monitoring
process recognizes its successful completion.

## Request

Respond with `hello`.

## Constraints

- Do not change repository files.
- Do not add dependencies.
- Follow the completion instruction supplied by the launcher.

## Acceptance Criteria

- The final response contains `hello`.
- The launcher completion instruction is followed only after the request is
  complete.
