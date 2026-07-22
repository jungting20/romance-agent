---
name: prepare-feature-ticket
description: Use only when the user explicitly invokes `$prepare-feature-ticket` to turn a feature idea into one local ready ticket. Do not use for ordinary feature discussion, design, planning, or implementation requests.
---

# Prepare Feature Ticket

Follow this recipe in order. Treat design approval and the later implementation
package approval as separate user decisions; never infer either approval.
Never claim a command was run, a file was checked, or a result exists unless it was actually observed.

1. Confirm that the request is an explicit invocation of
   `$prepare-feature-ticket`, then extract the feature idea. If the invocation
   or idea is absent, stop without creating or proposing a ticket.

2. Invoke `superpowers:brainstorming` for that idea and follow it completely.
   Write the resulting design under `docs/superpowers/specs/`, review it, and
   obtain explicit approval of the written design from the user. Preserve the
   approved repository-relative design path.

3. Invoke `superpowers:writing-plans` from that approved design and follow it
   completely. Write the detailed implementation plan under
   `docs/superpowers/plans/`. Review the completed written plan and preserve its
   repository-relative path, but do not request approval yet.

4. Derive a non-empty title and implementation-scope summary solely from the
   approved design and the completed written plan. Do not infer scope or add
   guessed UI, data, accessibility, error, or testing work. Derive a non-empty
   worktree branch from the same approved scope using the repository convention
   `feature/<한글-기능-이름>`. Keep the Korean feature name short, separate words
   with single hyphens, and do not use whitespace or an additional `/`. Build a
   non-empty implementation prompt from the approved repository-relative design
   and plan paths using this exact structure:

   ```text
   다음 승인된 문서를 authoritative implementation input으로 사용해 기능을 구현해줘.
   brainstorming과 writing-plans는 다시 수행하지 말고,
   feature-development의 전체 구현·검토·검증 절차를 따라줘.
   티켓에 없는 범위를 추측해서 추가하지 마.
   - 설계: <approved design path>
   - 구현 계획: <approved plan path>
   ```

   The prompt must name the `feature-development` skill and contain both
   approved document paths. Do not replace either path with a summary, an
   absolute path, or an unapproved location.

5. Present the written implementation plan, title, summary, worktree branch,
   and implementation prompt together during implementation-plan review. Ask
   for one explicit approval covering all five as ready for implementation and
   registration. Ambiguous, partial, or implied approval is not approval.
   If the user requests changes to any of the five, revise the affected values,
   present all five together again, and ask for a new explicit
   approval.

6. Do not register if either artifact is absent, either approval is missing,
   the title, summary, worktree branch, or prompt is empty, the worktree branch
   does not follow `feature/<한글-기능-이름>`, or the prompt does not name
   `feature-development` and contain both approved document paths. If the user
   asks to register early, state the unmet approval, artifact, branch, or prompt
   prerequisite and do not call
   `zellij-agent ticket-worker add`. If the user cancels at any point, stop
   without creating or proposing a ticket. Never invent a draft or call an
   unapproved package registration-ready.

7. Work from the repository root. Verify that the ticket-worker CLI is
   available:

   ```sh
   zellij-agent ticket-worker --help
   git check-ref-format --branch "$worktree_branch"
   ```

   Stop if the branch validation fails or the value does not begin with
   `feature/`. Then run `zellij-agent ticket-worker list --json`. If and only if
   it reports that ticket-worker is not initialized, run
   `zellij-agent ticket-worker init` once and continue. Stop on an unavailable
   CLI or any other initialization check failure.

8. Register only the jointly approved values and paths with shell-safe
   arguments. Substitute the current run's approved title, summary, design
   path, plan path, worktree branch, and implementation prompt for these
   variables:

   ```sh
   ticket_json=$(
     zellij-agent ticket-worker add \
       --title "$title" \
       --summary "$summary" \
       --spec "$spec_path" \
       --plan "$plan_path" \
       --worktree-branch "$worktree_branch" \
       --prompt "$prompt" \
       --json
   )
   ```

9. Parse `ticket_json` and verify the returned ticket has status `ready`, its
   `worktree_branch` exactly matches the jointly approved worktree branch, and
   its prompt exactly matches the jointly approved implementation prompt.
   Report its ID, title, design path, plan path, worktree branch, and prompt. If
   `zellij-agent ticket-worker add` returns the JSON error code `duplicate`, do
   not modify the database manually. Run
   `zellij-agent ticket-worker list --json`, select the item whose `plan_path`
   exactly matches the approved repository-relative `plan_path`, and verify
   that its `worktree_branch` and prompt exactly match the jointly approved
   values before reporting that existing ticket. If no exact plan, branch, and
   prompt match exists or the command fails for another reason, stop and report
   the failure without claiming that a ticket was registered.
   In a dry run, describe the intended duplicate-plan recovery and stop without
   claiming any command, file, or result outcome.
