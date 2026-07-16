---
name: prepare-feature-ticket
description: Use only when the user explicitly invokes `$prepare-feature-ticket` to turn a feature idea into one local ready ticket. Do not use for ordinary feature discussion, design, planning, or implementation requests.
---

# Prepare Feature Ticket

Follow this recipe in order. Treat the design and implementation-plan approvals
as separate user decisions; never infer either approval.

1. Confirm that the request is an explicit invocation of
   `$prepare-feature-ticket`, then extract the feature idea. If the invocation
   or idea is absent, stop without creating or proposing a ticket.

2. Invoke `superpowers:brainstorming` for that idea and follow it completely.
   Write the resulting design under `docs/superpowers/specs/`, review it, and
   obtain explicit approval of the written design from the user. Preserve the
   approved repository-relative design path.

3. Invoke `superpowers:writing-plans` from that approved design and follow it
   completely. Write the detailed implementation plan under
   `docs/superpowers/plans/`.
   Review it and obtain explicit approval of the written implementation plan from the user.
   Preserve the approved repository-relative plan path.

4. Derive a non-empty title and implementation-scope summary solely from the
   approved design and plan. Present both values before registration; they must
   describe the approved implementation scope, not guessed UI, data,
   accessibility, error, or testing work.

5. Do not register if either artifact is absent, either approval is missing,
   the user cancels, or the title or summary is empty. Before the written plan
   has been approved, do not invent a draft or call one registration-ready.
   Stop and state the unmet prerequisite without creating a ticket.

6. Work from the repository root. If `.local/bin/ra-ticket` is absent, build
   it from `tools/ra-ticket/` before continuing:

   ```sh
   mkdir -p .local/bin
   (cd tools/ra-ticket && mise exec -- go build -o ../../.local/bin/ra-ticket ./cmd/ra-ticket)
   ```

7. Register only the approved values and paths with shell-safe arguments.
   Substitute the current run's approved title, summary, design path, and plan
   path for these variables:

   ```sh
   ticket_json=$(
     .local/bin/ra-ticket add \
       --title "$title" \
       --summary "$summary" \
       --spec "$spec_path" \
       --plan "$plan_path" \
       --json
   )
   ```

8. Parse `ticket_json` and verify the returned ticket has status `ready`.
   Report its ID, title, design path, and plan path. If `ra-ticket add` reports
   a duplicate plan, do not modify the database manually. Run
   `.local/bin/ra-ticket list --json`, select the item whose `plan_path`
   exactly matches the approved repository-relative `plan_path`, and report
   that existing ticket instead. If no exact match exists or the command fails
   for another reason, stop and report the failure without claiming that a
   ticket was registered.
