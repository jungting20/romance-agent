#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skill_file=${1:-"$script_dir/../SKILL.md"}

fail() {
  printf 'prepare-feature-ticket skill: FAIL: %s\n' "$1" >&2
  exit 1
}

[ -f "$skill_file" ] || fail "missing SKILL.md"

require() {
  marker=$1
  label=$2
  grep -Fq -- "$marker" "$skill_file" || fail "missing $label: $marker"
}

require 'name: prepare-feature-ticket' 'skill name'
require 'only when the user explicitly invokes' 'explicit invocation gate'
require 'superpowers:brainstorming' 'brainstorming stage'
require 'docs/superpowers/specs/' 'design artifact path'
require 'explicit approval of the written design' 'design approval gate'
require 'superpowers:writing-plans' 'implementation planning stage'
require 'docs/superpowers/plans/' 'plan artifact path'
require 'Derive a non-empty title' 'title derivation stage'
require 'Present the written implementation plan, title, and summary together' 'registration value presentation'
require 'one explicit approval covering all' 'joint plan and registration approval gate'
require 'Do not register' 'negative registration gate'
require 'If the user asks to register early' 'early registration handling'
require 'Ambiguous, partial, or implied approval is not approval' 'ambiguous approval handling'
require 'If the user cancels at any point' 'cancellation handling'
require 'ra-ticket add' 'registration command'
require '--json' 'machine-readable registration'
require 'ready' 'initial ticket status'

brainstorm_line=$(grep -n -F 'superpowers:brainstorming' "$skill_file" | head -1 | cut -d: -f1)
design_approval_line=$(grep -n -F 'explicit approval of the written design' "$skill_file" | head -1 | cut -d: -f1)
plan_line=$(grep -n -F 'superpowers:writing-plans' "$skill_file" | head -1 | cut -d: -f1)
title_line=$(grep -n -F 'Derive a non-empty title' "$skill_file" | head -1 | cut -d: -f1)
present_line=$(grep -n -F 'Present the written implementation plan, title, and summary together' "$skill_file" | head -1 | cut -d: -f1)
plan_approval_line=$(grep -n -F 'one explicit approval covering all' "$skill_file" | head -1 | cut -d: -f1)
register_line=$(grep -n -F 'ra-ticket add' "$skill_file" | head -1 | cut -d: -f1)

[ "$brainstorm_line" -lt "$design_approval_line" ] || fail 'design approval must follow brainstorming'
[ "$design_approval_line" -lt "$plan_line" ] || fail 'writing plan must follow design approval'
[ "$plan_line" -lt "$title_line" ] || fail 'title derivation must follow writing plan'
[ "$title_line" -lt "$present_line" ] || fail 'title and summary presentation must follow derivation'
[ "$present_line" -lt "$plan_approval_line" ] || fail 'joint approval must follow title and summary presentation'
[ "$plan_approval_line" -lt "$register_line" ] || fail 'registration must follow plan approval'

printf 'prepare-feature-ticket skill: OK\n'
