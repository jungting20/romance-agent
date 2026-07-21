---
name: prepare-feature-ticket-fast
description: Use only when the user explicitly invokes `$prepare-feature-ticket-fast` to register a small, clear Romance Agent task directly as a ready ticket without approved spec or plan artifacts. Do not use for ordinary discussion, implementation, or work requiring FULL mode.
---

# Prepare Feature Ticket Fast

Register one bounded FAST-mode task without running brainstorming or
writing-plans and without creating spec or plan documents. Treat the explicit
skill invocation as authorization to register after the task passes the FAST
eligibility check.

## Workflow

1. Confirm the request explicitly invokes `$prepare-feature-ticket-fast` and
   contains a non-empty task. Otherwise stop without proposing or registering a
   ticket.

2. Check FAST eligibility against the repository `AGENTS.md`. This skill is
   eligible only when the work is clear, small, and can be completed with a
   minimal focused change. Do not use brainstorming, writing-plans, a worktree,
   or subagents. Stop and direct the user to `$prepare-feature-ticket` when the
   task involves any of the following:

   - new product functionality or a structural change;
   - three or more major files or modules;
   - an unclear boundary or a material design decision;
   - a consumer-facing API contract change;
   - any explicit FULL-mode request.

3. Work from the repository root. Inspect only enough repository context to
   make the task executable. Read applicable `AGENTS.md` files and relevant
   project or domain documentation. If `.codegraph/` exists, use CodeGraph
   before grep, find, or broad file reads when locating or understanding code.
   Do not modify application code or create spec/plan artifacts.

4. Derive these non-empty values only from the user's request and observed
   repository facts:

   - `title`: a concise task title;
   - `summary`: the intended change, boundary, exclusions, and expected
     verification;
   - `prompt`: an implementation-ready instruction using this exact shape,
     omitting only an exclusion that truly does not apply:

   ```text
   FAST 모드로 다음 작업을 처리해줘.
   저장소의 AGENTS.md를 준수하고 brainstorming, writing-plans, worktree,
   subagent를 사용하지 마. 최소 수정 후 관련 검증을 실행해.

   작업:
   <observed task scope>

   완료 조건:
   - <concrete acceptance criterion>

   검증:
   - <observed relevant command or check>

   제외 범위:
   - <explicit exclusion>
   ```

   Do not invoke or name `feature-development` in the prompt because its FULL
   workflow conflicts with FAST mode. Do not invent UI, API, domain, testing,
   or documentation scope that the request and repository do not establish.

5. Verify the CLI and queue before registration:

   ```sh
   zellij-agent ticket-worker --help
   zellij-agent ticket-worker list --json
   ```

   Run `zellij-agent ticket-worker init` once only when the list command
   specifically reports that ticket-worker is not initialized. Stop on an
   unavailable CLI or any other failure.

6. Register the derived values with shell-safe arguments. Do not pass `--spec`
   or `--plan` and do not create placeholder artifacts:

   ```sh
   ticket_json=$(
     zellij-agent ticket-worker fast-add \
       --title "$title" \
       --summary "$summary" \
       --prompt "$prompt" \
       --json
   )
   ```

7. Parse `ticket_json`. Report success only when the returned ticket has status
   `ready` and its title, summary, and prompt exactly match the submitted
   values. Report the ticket ID, title, summary, and complete prompt. On any
   command, JSON, or value mismatch, stop and report the failure without
   claiming registration succeeded. In a dry run, show the intended values and
   command behavior but do not call `fast-add` or claim a ticket exists.

## Common Mistakes

- Creating lightweight spec or plan files even though `fast-add` does not need
  them.
- Registering an ambiguous or FULL-mode task as FAST.
- Asking for another approval after an explicit invocation.
- Expanding the prompt with guessed implementation scope.
- Reporting success without comparing the returned prompt exactly.
