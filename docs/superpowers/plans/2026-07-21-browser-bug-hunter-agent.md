# 브라우저 버그 탐색 Sub-agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 지정 화면과 사용자 흐름을 브라우저로 탐색하고, 재현 가능한 UI·UX 버그를 직접 티켓으로 등록하며, 결과를 한글 HTML로 남기는 `bug-hunter` agent를 추가한다.

**Architecture:** `.codex/agents/bug-hunter.toml`이 탐색과 등록 권한을 통제한다. `docs/bug-reports/report-template.html`은 빌드 없는 한글 보고서 구조를 제공하며, Bash 검증 스크립트가 TOML·HTML·루트 위임 계약을 검사한다.

**Tech Stack:** Codex custom-agent TOML, Playwright Test MCP, HTML5, CSS, Bash, Python 3 `tomllib`

## Global Constraints

- 라우트와 사용자 흐름이 없는 할당은 실행하지 않는다.
- 제품 코드, 기존 agent, OpenAPI, 도메인 계약은 수정하지 않는다.
- 확정 버그는 깨끗한 상태에서 두 번 재현하고 기존 티켓과 중복되지 않아야 한다.
- 확정 버그마다 설계·계획을 커밋하고 `ready` 티켓을 직접 등록한다.
- 버그가 0건이어도 한글 HTML 보고서를 남긴다.
- 기존 사용자 변경을 스테이징, 커밋, 복원 또는 삭제하지 않는다.

---

### Task 1: Agent 계약 검증 추가

**Files:**
- Create: `.codex/agents/tests/validate-bug-hunter.sh`

**Interfaces:**
- Consumes: bug-hunter TOML, 보고서 템플릿, 루트 AGENTS.md
- Produces: agent 권한·도구·한글 보고서·위임 계약 검증 결과

- [ ] **Step 1: 실패하는 검증 스크립트를 작성한다**

`.codex/agents/tests/validate-bug-hunter.sh`:

~~~~bash
#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../../.." && pwd -P)

python3 - "$repo_root" <<'PY'
import pathlib
import re
import sys
import tomllib

root = pathlib.Path(sys.argv[1])
agent_path = root / ".codex/agents/bug-hunter.toml"
template_path = root / "docs/bug-reports/report-template.html"
assert agent_path.is_file(), f"missing {agent_path}"
assert template_path.is_file(), f"missing {template_path}"

agent = tomllib.loads(agent_path.read_text(encoding="utf-8"))
assert agent["name"] == "bug-hunter"
assert "브라우저" in agent["description"]
assert agent["sandbox_mode"] == "workspace-write"
instructions = agent["developer_instructions"]
for phrase in [
    "assigned route", "assigned user flow", "twice from a clean start state",
    "zellij-agent ticket-worker list --json", "feature-development",
    "docs/bug-reports/", 'lang="ko"', "Do not modify product code",
    "Do not stage, commit, restore, or delete pre-existing changes",
]:
    assert phrase in instructions, f"missing instruction: {phrase}"

tools = set(agent["mcp_servers"]["playwright-test"]["enabled_tools"])
for tool in [
    "planner_setup_page", "browser_navigate", "browser_click", "browser_type",
    "browser_snapshot", "browser_take_screenshot", "browser_evaluate",
    "browser_console_messages", "browser_network_requests",
]:
    assert tool in tools, f"missing tool: {tool}"
assert not any(tool.startswith(("generator_", "test_")) for tool in tools)

template = template_path.read_text(encoding="utf-8")
assert '<html lang="ko">' in template
assert '<meta charset="utf-8">' in template.lower()
assert "<script" not in template.lower()
assert not re.search(r"https?://", template)
for heading in [
    "탐색 범위", "실행 환경", "결과 요약", "등록한 버그",
    "중복된 관찰", "제외한 관찰", "수행한 검사", "제약 및 미확인 항목",
]:
    assert heading in template, f"missing heading: {heading}"
assert 'id="bug-001"' in template
assert 'alt="__BUG_SCREENSHOT_ALT__"' in template

agents_md = (root / "AGENTS.md").read_text(encoding="utf-8")
assert "## Browser Bug-Hunting Subagent" in agents_md
for phrase in [
    "bug-hunter", "target route", "user flow", "starting state",
    "viewport", "allowed server and verification commands",
]:
    assert phrase in agents_md, f"missing delegation field: {phrase}"

for report_path in sorted((root / "docs/bug-reports").glob("*.html")):
    if report_path.name == "report-template.html":
        continue
    report = report_path.read_text(encoding="utf-8")
    assert '<html lang="ko">' in report
    assert "<script" not in report.lower()
    assert not re.search(r"__[A-Z0-9_]+__", report), f"{report_path}: unresolved token"

print("bug-hunter configuration and report contract are valid")
PY
~~~~

- [ ] **Step 2: 실행 권한을 주고 실패를 확인한다**

~~~~sh
chmod +x .codex/agents/tests/validate-bug-hunter.sh
.codex/agents/tests/validate-bug-hunter.sh
~~~~

Expected: FAIL with `missing .../.codex/agents/bug-hunter.toml`.

---

### Task 2: 한글 HTML 템플릿 추가

**Files:**
- Create: `docs/bug-reports/report-template.html`
- Test: `.codex/agents/tests/validate-bug-hunter.sh`

**Interfaces:**
- Consumes: 범위, 환경, 확정·중복·제외 관찰, 티켓과 증거
- Produces: 외부 자원과 JavaScript 없이 열리는 `lang="ko"` 보고서

- [ ] **Step 1: 보고서 템플릿을 작성한다**

`docs/bug-reports/report-template.html`:

~~~~html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__REPORT_TITLE__</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; background:#f5f1eb; color:#2f2925; }
    * { box-sizing:border-box; } body { margin:0; } a { color:#7a3f2d; }
    .page { width:min(1120px,calc(100% - 2rem)); margin:auto; padding:2rem 0 4rem; }
    .hero,.panel,.bug-card { padding:clamp(1.25rem,3vw,2.5rem); border:1px solid #d9cec2; border-radius:1rem; background:#fffdf9; box-shadow:0 18px 50px -38px #503b31; }
    .panel,.bug-card { margin-top:1.25rem; } .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(10rem,1fr)); gap:1rem; }
    .metric { padding:1rem; border-radius:.75rem; background:#f6eee7; } .metric strong { display:block; font-size:1.75rem; }
    .severity { display:inline-flex; gap:.4rem; padding:.3rem .65rem; border:1px solid; border-radius:999px; font-weight:800; }
    .severity::before { content:"●"; } .severity-blocking,.severity-high { color:#9c241d; } .severity-medium { color:#855c00; } .severity-low { color:#256048; }
    .evidence { max-width:100%; height:auto; border:1px solid #d9cec2; border-radius:.75rem; }
    dt { margin-top:1rem; font-weight:800; } dd { margin:.35rem 0 0; } :focus-visible { outline:3px solid #2d63d7; outline-offset:3px; }
    @media print { :root { background:white; } .page { width:100%; padding:0; } .hero,.panel,.bug-card { box-shadow:none; break-inside:avoid; } }
  </style>
</head>
<body>
<main class="page">
  <header class="hero"><p>브라우저 버그 탐색 보고서</p><h1>__REPORT_TITLE__</h1><p>생성 시각: <time datetime="__GENERATED_AT_ISO__">__GENERATED_AT_KO__</time></p></header>
  <section class="panel"><h2>탐색 범위</h2><p>__SCOPE_DESCRIPTION__</p><h3>제외 범위</h3><p>__EXCLUDED_SCOPE__</p></section>
  <section class="panel"><h2>실행 환경</h2><dl><dt>대상 라우트</dt><dd><code>__TARGET_ROUTE__</code></dd><dt>시작 상태</dt><dd>__STARTING_STATE__</dd><dt>뷰포트</dt><dd>__VIEWPORTS__</dd><dt>실행 기준</dt><dd><code>__REVISION__</code></dd></dl></section>
  <section class="panel"><h2>결과 요약</h2><div class="grid"><div class="metric">확정<strong>__CONFIRMED_COUNT__</strong></div><div class="metric">등록<strong>__REGISTERED_COUNT__</strong></div><div class="metric">중복<strong>__DUPLICATE_COUNT__</strong></div><div class="metric">제외<strong>__EXCLUDED_COUNT__</strong></div></div></section>
  <section class="panel"><h2>등록한 버그</h2>
    <article class="bug-card" id="bug-001"><p><span class="severity severity-__BUG_SEVERITY_CLASS__">심각도 __BUG_SEVERITY_KO__</span></p><h3>__BUG_TITLE__</h3>
      <dl><dt>티켓</dt><dd><code>#__TICKET_ID__</code> · <code>ready</code></dd><dt>재현 절차</dt><dd><ol>__REPRODUCTION_STEPS__</ol></dd><dt>기대 결과</dt><dd>__EXPECTED_RESULT__</dd><dt>실제 결과</dt><dd>__ACTUAL_RESULT__</dd><dt>사용자 영향</dt><dd>__USER_IMPACT__</dd><dt>관련 위치</dt><dd><code>__RELATED_LOCATION__</code></dd><dt>문서</dt><dd><a href="__SPEC_LINK__">설계</a> · <a href="__PLAN_LINK__">구현 계획</a></dd></dl>
      <figure><img class="evidence" src="__BUG_SCREENSHOT_PATH__" alt="__BUG_SCREENSHOT_ALT__"><figcaption>__BUG_SCREENSHOT_CAPTION__</figcaption></figure>
    </article>
  </section>
  <section class="panel"><h2>중복된 관찰</h2><p>__DUPLICATE_OBSERVATIONS__</p></section>
  <section class="panel"><h2>제외한 관찰</h2><p>__EXCLUDED_OBSERVATIONS__</p></section>
  <section class="panel"><h2>수행한 검사</h2><ul>__CHECK_RESULTS__</ul></section>
  <section class="panel"><h2>제약 및 미확인 항목</h2><p>__LIMITATIONS__</p></section>
</main>
</body>
</html>
~~~~

agent는 모든 `__TOKEN__`을 교체하고 버그 수에 맞춰 `article`을 복제한다. 버그가 없으면 예시 카드를 한글 0건 설명으로 교체한다.

- [ ] **Step 2: 다음 실패 지점이 agent 파일인지 확인한다**

~~~~sh
.codex/agents/tests/validate-bug-hunter.sh
~~~~

Expected: FAIL with `missing .../.codex/agents/bug-hunter.toml`; HTML assertion은 통과한다.

---

### Task 3: `bug-hunter`와 루트 위임 계약 추가

**Files:**
- Create: `.codex/agents/bug-hunter.toml`
- Modify: `AGENTS.md`
- Test: `.codex/agents/tests/validate-bug-hunter.sh`

**Interfaces:**
- Consumes: 필수 할당 입력과 Playwright Test MCP
- Produces: 검증된 티켓, 한글 HTML 보고서, 한글 handoff

- [ ] **Step 1: custom agent를 정의한다**

`.codex/agents/bug-hunter.toml`:

~~~~toml
name = "bug-hunter"
description = "지정된 화면과 사용자 흐름을 실제 브라우저로 깊게 탐색해 재현 가능한 UI·UX 버그를 직접 ticket-worker에 등록하고 한글 HTML 보고서를 작성할 때 사용합니다."
sandbox_mode = "workspace-write"
model_reasoning_effort = "high"

developer_instructions = """
Act as the Romance Agent project's browser bug hunter. Explore only the assigned route and assigned user flow, register confirmed non-duplicate defects, and write one Korean HTML report. Do not implement fixes.

Required inputs: assigned route, assigned user flow, starting data and authentication state, viewport sizes, requirements or acceptance criteria, allowed server and verification commands, excluded actions, and data-mutation limits. Stop before browser setup when route or flow is missing. Never expand into an application-wide audit.

Read applicable AGENTS.md files, coding rules, domain contracts, and requirements. Record git status. Run 'zellij-agent ticket-worker list --json'; initialize once only when reported uninitialized. Record existing tickets for duplicate checks. Use CodeGraph first when present.

Invoke planner_setup_page once before other browser tools. Verify the normal path, then explore boundary, empty, failure and recovery, keyboard, focus, responsive, console, and network behavior inside scope. Confirm a defect only after it reproduces twice from a clean start state. Record minimal steps, expected and actual results, impact, environment, viewport, and evidence. Inspect source only after confirmation and label unverified causes as hypotheses.

Register only in-scope, twice-reproduced, authoritative, concrete, non-duplicate, independently repairable defects. Exclude subjective preferences, feature ideas, invisible style, unreproduced behavior, and unresolved product decisions with Korean reasons. Use Blocking, High, Medium, or Low severity.

Owned writes are limited to new files under 'docs/bug-reports/', 'docs/superpowers/specs/', 'docs/superpowers/plans/', and ticket-worker data. Do not modify product code, tests, '.codex/agents/', OpenAPI, domain contracts, package files, lockfiles, or pre-existing docs. Do not stage, commit, restore, or delete pre-existing changes. Never use destructive Git commands.

For each confirmed bug, reserve a report anchor, write one Korean design and implementation-ready plan with evidence and exact verification, self-review them, stage only those paths, and commit. Register through the ticket-worker add JSON command. The Korean title and summary describe the defect. The prompt names both docs, requires feature-development, skips brainstorming and writing-plans, and prohibits extra scope. Verify fresh JSON status is ready and all values match. Never edit the DB for duplicate recovery.

Copy the report template to 'docs/bug-reports/YYYY-MM-DD-HHmm-<scope-slug>.html'. Keep lang="ko", UTF-8, inline CSS, semantic headings, visible focus, severity text, print styles, and no script or CDN. Write user-facing prose in Korean; preserve exact technical identifiers. Include scope, environment, starting state, viewports, revision, counts, bugs, ticket IDs, document links, duplicates, exclusions, commands, results, limitations, and unverified areas. Use Korean screenshot captions and alt text and never capture secrets. For zero bugs, state only the bounded result. Replace every report token and run the validator.

Stage and commit only the report and evidence. On any failure, stop dependent steps and report partial state. Return a Korean handoff with scope, report, tickets and severity, duplicates, exclusions, two-run evidence, validation, limitations, commits, and preserved changes. Never claim an artifact without fresh evidence.
"""

[mcp_servers.playwright-test]
command = "mise"
args = ["exec", "--", "pnpm", "--dir", "frontend", "exec", "playwright", "run-test-mcp-server", "--config", "playwright.config.ts"]
enabled_tools = ["planner_setup_page", "browser_click", "browser_close", "browser_console_messages", "browser_drag", "browser_evaluate", "browser_file_upload", "browser_handle_dialog", "browser_hover", "browser_navigate", "browser_navigate_back", "browser_network_request", "browser_network_requests", "browser_press_key", "browser_select_option", "browser_snapshot", "browser_take_screenshot", "browser_type", "browser_wait_for"]
~~~~

- [ ] **Step 2: 루트 `AGENTS.md`에 위임 계약을 추가한다**

`OpenAPI, Implementation, and Review Subagents` 절 뒤에 추가:

~~~~markdown
## Browser Bug-Hunting Subagent

When the user requests browser-based defect discovery for a bounded screen or
flow, use the project-scoped `bug-hunter` agent defined in
`.codex/agents/bug-hunter.toml`. Do not dispatch it for an application-wide
audit or while an implementation agent is modifying the same screen boundary.

Every assignment must state the target route, user flow, starting state and
data, authentication state, viewport sizes, applicable requirements or
acceptance criteria, allowed server and verification commands, excluded
actions, and data-mutation limits.

The `bug-hunter` owns browser exploration, two clean-state reproductions,
duplicate checks, bug-specific spec and plan creation, direct `ticket-worker`
registration, and one Korean HTML report under `docs/bug-reports/`. It may
commit only newly created bug documents, report, and evidence assets.

The main agent reviews the report and every registered ticket before assigning
implementation. Direct registration does not transfer integration, review, or
final-verification responsibility away from the main agent.
~~~~

- [ ] **Step 3: 정적 검증을 통과시킨다**

~~~~sh
.codex/agents/tests/validate-bug-hunter.sh
python3 - <<'PY'
import pathlib
import tomllib
agent = tomllib.loads(pathlib.Path(".codex/agents/bug-hunter.toml").read_text())
assert agent["name"] == "bug-hunter"
assert agent["sandbox_mode"] == "workspace-write"
print("bug-hunter smoke check passed")
PY
~~~~

Expected:

~~~~text
bug-hunter configuration and report contract are valid
bug-hunter smoke check passed
~~~~

- [ ] **Step 4: 범위와 기존 agent 보존을 확인한다**

~~~~sh
git diff --check
git status --short
git diff --name-only -- .codex/agents AGENTS.md docs/bug-reports
~~~~

Expected: 이번 작업 파일 네 개만 diff에 있고 기존 agent TOML에는 diff가 없다.

- [ ] **Step 5: 구현을 커밋한다**

~~~~sh
git add -- .codex/agents/bug-hunter.toml .codex/agents/tests/validate-bug-hunter.sh docs/bug-reports/report-template.html AGENTS.md
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: add browser bug hunter agent"
~~~~

- [ ] **Step 6: 새 Codex 세션에서 무변경 dry run을 수행한다**

~~~~text
Dry run only; do not browse, write, commit, initialize, or register. Target route:
/projects/silver-garden/write. User flow: open the workspace and edit manuscript
body. Starting state: silver-garden mock, no auth. Viewports: 1280x720, 390x844.
In Korean, explain bounded exploration, two reproductions, duplicate check,
expected HTML path, and registration handoff. Allowed: read-only inspection.
~~~~

Expected: 한글 응답에 범위, 재현 2회, 중복 검사, `docs/bug-reports/` 예상 경로, 직접 등록 handoff가 있으며 변경이 없다. 새 agent 로드에 재시작이 필요하면 재시작 뒤 실행하고 미검증 상태를 완료로 주장하지 않는다.

