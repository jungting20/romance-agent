#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
skill_file=${1:-"$script_dir/../SKILL.md"}

fail() {
  printf 'feature-development skill structure: FAIL: %s\n' "$1" >&2
  exit 1
}

if [ ! -f "$skill_file" ]; then
  fail "skill file not found: $skill_file"
fi

frontmatter_delimiters=$(awk '$0 == "---" { count += 1 } END { print count + 0 }' "$skill_file")
if [ "$frontmatter_delimiters" -lt 2 ]; then
  fail "YAML frontmatter must have opening and closing delimiters"
fi

require_fixed() {
  marker=$1
  label=$2
  if ! grep -Fq -- "$marker" "$skill_file"; then
    fail "missing $label: $marker"
  fi
}

require_fixed 'name: feature-development' 'skill name'
require_fixed 'description: Use when' 'trigger description'
require_fixed 'new screen' 'new-screen choice'
require_fixed 'existing screen' 'existing-screen choice'
require_fixed 'database' 'database choice'
require_fixed 'file' 'file choice'
require_fixed 'recommended approach' 'recommendation choice'
require_fixed 'one at a time' 'question sequencing'
require_fixed 'implementation brief' 'implementation brief'
require_fixed 'user approves' 'user approval gate'
require_fixed '`openapi`' 'OpenAPI agent'
require_fixed '`docs/api/openapi.yaml`' 'OpenAPI ownership path'
require_fixed 'exact proposed baseline' 'main-agent baseline approval'
require_fixed '`frontend`' 'frontend agent'
require_fixed '`backend`' 'backend agent'
require_fixed 'parallel' 'parallel delegation'
require_fixed 'non-overlapping' 'disjoint ownership'
require_fixed '`operationId`' 'operation assignment'
require_fixed '`docs/domains/*.md`' 'domain-document synchronization'
require_fixed 'mise exec -- pnpm check' 'frontend check command'
require_fixed 'mise exec -- pnpm build' 'frontend build command'

printf 'feature-development skill structure: OK\n'
