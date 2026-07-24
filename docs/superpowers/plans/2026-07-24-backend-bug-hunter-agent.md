# Backend 버그 탐색 전용 에이전트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 하나의 API operation 또는 backend use case를 격리 탐색하고, 두 번 재현한 신규 결함만 티켓과 한글 HTML 보고서로 남기는 `backend-bug-hunter` custom agent를 추가한다.

**Architecture:** 전용 TOML agent가 실행 계약과 안전 경계를 소유하고, 전용 HTML 템플릿이 backend 증거 구조를 정의한다. 독립 Bash/Python validator가 agent·루트 정책·HTML·격리·redaction·partial-handoff 계약을 검증하며, 기존 browser `bug-hunter`와 `backend-review`는 변경하지 않는다.

**Tech Stack:** Codex custom-agent TOML, Bash, Python 3.13 표준 `tomllib`·`html.parser`, HTML5, CSS, Git

## Global Constraints

- 탐색 대상은 정확히 하나의 `operationId` 또는 하나의 명시적 backend use case다.
- 실제 운영 데이터, 외부 provider, 공유 DB와 공유 파일을 사용하지 않는다.
- 제품 코드와 테스트, OpenAPI, domain contract, 기존 browser `bug-hunter`, `backend-review`, `backend/AGENTS.md`를 수정하지 않는다.
- 결함은 독립된 두 clean run에서 재현하고 fresh ticket 목록에서 중복이 아님을 확인해야 등록한다.
- 보고서의 요청·응답·로그·저장 전후 증거는 민감정보를 제거한다.
- 실행 또는 등록 실패 시 실제 artifact, ticket, cleanup과 미완료 단계를 partial handoff로 반환한다.
- 커밋 메시지는 한글로 작성한다.
- 승인된 설계는 `docs/superpowers/specs/2026-07-24-backend-bug-hunter-agent-design.md`다.

---

### Task 1: 전용 validator의 실패하는 계약 테스트 추가

**Files:**
- Create: `.codex/agents/tests/validate-backend-bug-hunter.sh`
- Reference: `docs/superpowers/specs/2026-07-24-backend-bug-hunter-agent-design.md`

**Interfaces:**
- Consumes: `.codex/agents/backend-bug-hunter.toml`, `docs/bug-reports/backend-report-template.html`, 루트 `AGENTS.md`, 생성된 `*-backend-*.html` 보고서
- Produces: agent 역할·입력·격리·redaction·등록·partial handoff와 HTML evidence 계약의 결정적 검증 결과

- [ ] **Step 1: 저장소 mise 설정을 이 worktree에서 신뢰한다**

Run:

```sh
mise trust mise.toml
mise exec -- python --version
```

Expected: Python `3.13.14` 또는 저장소 `mise.toml`이 고정한 호환 Python 3.13이 출력된다.

- [ ] **Step 2: 실패하는 전용 validator를 작성한다**

Create `.codex/agents/tests/validate-backend-bug-hunter.sh` with:

```bash
#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../../.." && pwd -P)

python3 - "$repo_root" <<'PY'
import pathlib
import re
import sys
import tomllib
from html.parser import HTMLParser
from urllib.parse import urlsplit

root = pathlib.Path(sys.argv[1])
agent_path = root / ".codex/agents/backend-bug-hunter.toml"
template_path = root / "docs/bug-reports/backend-report-template.html"
assert template_path.is_file(), f"missing {template_path}"
assert agent_path.is_file(), f"missing {agent_path}"

agent = tomllib.loads(agent_path.read_text(encoding="utf-8"))
assert agent["name"] == "backend-bug-hunter"
assert "operationId" in agent["description"]
assert "backend use case" in agent["description"]
assert agent["sandbox_mode"] == "workspace-write"
assert agent["model_reasoning_effort"] == "high"
assert "mcp_servers" not in agent, "backend bug hunter must not inherit browser MCP tools"

instructions = re.sub(r"\s+", " ", agent["developer_instructions"])
required_agent_phrases = [
    "exactly one operationId or one explicit backend use case",
    "entry point",
    "main-agent-approved OpenAPI baseline",
    "relevant domain contracts",
    "starting fixture and authentication state",
    "temporary database and file paths",
    "isolation and cleanup method",
    "allowed commands",
    "excluded scope",
    "data-mutation limits",
    "error, concurrency, and retry scenarios",
    "Stop before setup",
    "normal, boundary, validation, 404, 409, 422, and 500",
    "persistence rollback, concurrency, retry, provider failure",
    "sensitive log exposure",
    "twice from independent clean states",
    "zellij-agent ticket-worker list --json",
    "Immediately before registration",
    "actual production data",
    "external provider",
    "shared database",
    "[REDACTED]",
    "request and response",
    "sanitized logs",
    "storage state before and after",
    "partial handoff",
    "Do not modify product code or tests",
    "Do not modify docs/api/openapi.yaml or docs/domains/",
    "Do not modify .codex/agents/bug-hunter.toml or .codex/agents/backend-review.toml",
    "Do not modify backend/AGENTS.md",
    "zellij-agent ticket-worker add",
    "zellij-agent ticket-worker fast-add",
    "FAST 모드로 처리한다",
    "Never edit the ticket database",
]
for phrase in required_agent_phrases:
    assert phrase in instructions, f"missing backend-bug-hunter instruction: {phrase}"

required_headings = {
    "탐색 범위",
    "실행 계약",
    "격리 환경",
    "시나리오 결과",
    "결과 요약",
    "등록한 버그",
    "중복된 관찰",
    "제외한 관찰",
    "수행한 검사",
    "실패 및 부분 완료",
    "제약 및 미확인 항목",
}
url_attributes = {"href", "src", "srcset", "action", "poster"}
secret_patterns = [
    re.compile(r"authorization\s*[:=](?!\s*\[REDACTED\])\s*[^<\n]+", re.IGNORECASE),
    re.compile(r"bearer\s+(?!\[REDACTED\])[-._~+/A-Za-z0-9]+=*", re.IGNORECASE),
    re.compile(r"(?:cookie|api[_-]?key|provider[_-]?secret)\s*[:=](?!\s*\[REDACTED\])\s*[^<\n]+", re.IGNORECASE),
]


class BackendReportInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lang = None
        self.utf8 = False
        self.viewport = False
        self.script = False
        self.external = []
        self.headings = []
        self._heading = None
        self.bug_anchors = []
        self.run_numbers = []
        self.isolation_marker = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang")
        elif tag == "meta":
            self.utf8 |= values.get("charset", "").lower() == "utf-8"
            self.viewport |= values.get("name", "").lower() == "viewport"
            self.isolation_marker |= (
                values.get("name") == "backend-bug-hunter-isolation"
                and values.get("content") == "run-specific"
            )
        elif tag == "script":
            self.script = True
        elif tag == "h2":
            self._heading = []
        elif tag == "article" and "bug-card" in values.get("class", "").split():
            self.bug_anchors.append(values.get("id"))
        elif tag == "section" and "run-evidence" in values.get("class", "").split():
            self.run_numbers.append(values.get("data-run"))
        for name, value in values.items():
            if name not in url_attributes or not value:
                continue
            candidates = value.split(",") if name == "srcset" else [value]
            for candidate in candidates:
                url = candidate.strip().split()[0]
                parsed = urlsplit(url)
                if parsed.scheme or parsed.netloc or url.startswith("//"):
                    self.external.append(url)

    def handle_endtag(self, tag):
        if tag == "h2" and self._heading is not None:
            self.headings.append("".join(self._heading).strip())
            self._heading = None

    def handle_data(self, data):
        if self._heading is not None:
            self._heading.append(data)


def validate_report(html: str, *, source: str, generated: bool) -> None:
    inspector = BackendReportInspector()
    inspector.feed(html)
    assert inspector.lang == "ko", f'{source}: missing lang="ko"'
    assert inspector.utf8, f"{source}: missing UTF-8 metadata"
    assert inspector.viewport, f"{source}: missing viewport metadata"
    assert inspector.isolation_marker, f"{source}: missing run-specific isolation marker"
    assert not inspector.script, f"{source}: script is forbidden"
    assert not inspector.external, f"{source}: external resources are forbidden: {inspector.external}"
    assert not (required_headings - set(inspector.headings)), f"{source}: missing required headings"
    for pattern in secret_patterns:
        assert not pattern.search(html), f"{source}: raw sensitive value matched {pattern.pattern}"
    if not generated:
        assert 'id="bug-001"' in html, f"{source}: missing template bug anchor"
        assert 'data-run="1"' in html and 'data-run="2"' in html
        for token in [
            "__SANITIZED_REQUEST__",
            "__SANITIZED_RESPONSE__",
            "__SANITIZED_LOGS__",
            "__STORAGE_BEFORE__",
            "__STORAGE_AFTER__",
            "__PARTIAL_STATE__",
            "__CLEANUP_RESULT__",
        ]:
            assert token in html, f"{source}: missing template token {token}"
        return

    assert not re.search(r"__[A-Z0-9_]+__", html), f"{source}: unresolved token"
    if inspector.bug_anchors:
        assert all(re.fullmatch(r"bug-\d{3}", anchor or "") for anchor in inspector.bug_anchors)
        assert len(inspector.bug_anchors) == len(set(inspector.bug_anchors))
        assert inspector.run_numbers.count("1") >= len(inspector.bug_anchors)
        assert inspector.run_numbers.count("2") >= len(inspector.bug_anchors)
        for phrase in ["정제된 요청", "정제된 응답", "정제 로그", "저장 전 상태", "저장 후 상태"]:
            assert phrase in html, f"{source}: missing evidence label {phrase}"
    else:
        assert re.search(r"등록할\s+확정\s+결함이\s+없", html), f"{source}: missing bounded zero-result marker"
    if "실패 단계" in html:
        for phrase in ["완료 단계", "미완료 단계", "임시 경로", "정리 결과", "재개 조건"]:
            assert phrase in html, f"{source}: incomplete partial handoff: {phrase}"


template = template_path.read_text(encoding="utf-8")
validate_report(template, source=str(template_path), generated=False)

fixture_sections = "".join(f"<section><h2>{heading}</h2></section>" for heading in sorted(required_headings))
valid_fixture = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><meta name="backend-bug-hunter-isolation" content="run-specific"></head>
<body>{fixture_sections}<article class="bug-card" id="bug-001">
<section class="run-evidence" data-run="1">정제된 요청 Authorization: [REDACTED] 정제된 응답 정제 로그 저장 전 상태 저장 후 상태</section>
<section class="run-evidence" data-run="2">정제된 요청 Authorization: [REDACTED] 정제된 응답 정제 로그 저장 전 상태 저장 후 상태</section>
</article></body></html>'''
zero_fixture = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><meta name="backend-bug-hunter-isolation" content="run-specific"></head>
<body>{fixture_sections}<p>이 제한된 범위에서 등록할 확정 결함이 없습니다.</p></body></html>'''
partial_fixture = valid_fixture.replace(
    "</body>",
    "<p>실패 단계: report validation / 완료 단계: run 1 / 미완료 단계: registration / 임시 경로: run-001 / 정리 결과: 완료 / 재개 조건: fixture 수정</p></body>",
)


def rejected(name: str, html: str, message: str) -> None:
    try:
        validate_report(html, source=f"fixture:{name}", generated=True)
    except AssertionError as error:
        assert message in str(error), f"fixture:{name}: unexpected assertion: {error}"
    else:
        raise AssertionError(f"fixture:{name}: unexpectedly accepted")


validate_report(valid_fixture, source="fixture:valid", generated=True)
validate_report(zero_fixture, source="fixture:zero", generated=True)
validate_report(partial_fixture, source="fixture:partial", generated=True)
rejected("bearer", valid_fixture.replace("Authorization: [REDACTED]", "Authorization: Bearer secret-token", 1), "raw sensitive")
rejected("cookie", valid_fixture.replace("정제 로그", "Cookie=session-secret 정제 로그", 1), "raw sensitive")
rejected("missing-run-two", valid_fixture.replace('data-run="2"', 'data-run="1"'), "")
rejected("unstable-anchor", valid_fixture.replace('id="bug-001"', 'id="backend-problem"'), "")
rejected("external-resource", valid_fixture.replace("</head>", '<script src="https://example.com/x.js"></script></head>'), "script is forbidden")
rejected(
    "shared-db",
    valid_fixture.replace('content="run-specific"', 'content="shared"'),
    "missing run-specific isolation marker",
)
rejected("unresolved-token", valid_fixture.replace("</body>", "<p>__LEFTOVER__</p></body>"), "unresolved token")
rejected("partial-without-state", valid_fixture.replace("</body>", "<p>실패 단계: setup</p></body>"), "incomplete partial handoff")

agents_md = re.sub(r"\s+", " ", (root / "AGENTS.md").read_text(encoding="utf-8"))
assert "## Backend Bug-Hunting Subagent" in (root / "AGENTS.md").read_text(encoding="utf-8")
for phrase in [
    "backend-bug-hunter",
    "exactly one `operationId` or one explicit backend use case",
    "approved OpenAPI baseline",
    "temporary database and file paths",
    "two independent clean-state reproductions",
    "request and response, sanitized logs, and storage state before and after",
    "partial handoff",
]:
    assert phrase in agents_md, f"missing root backend bug-hunter policy: {phrase}"

for report_path in sorted((root / "docs/bug-reports").glob("*-backend-*.html")):
    validate_report(report_path.read_text(encoding="utf-8"), source=str(report_path), generated=True)

print("backend report fixtures passed: 3 positive, 8 negative")
print("backend-bug-hunter configuration, policy, isolation, redaction, and report contract are valid")
PY
```

- [ ] **Step 3: 실행 권한을 설정하고 첫 실패를 확인한다**

Run:

```sh
chmod +x .codex/agents/tests/validate-backend-bug-hunter.sh
mise exec -- bash .codex/agents/tests/validate-backend-bug-hunter.sh
```

Expected: FAIL with `missing .../docs/bug-reports/backend-report-template.html`.

- [ ] **Step 4: 실패하는 validator만 커밋한다**

```sh
git add -- .codex/agents/tests/validate-backend-bug-hunter.sh
git commit -m "백엔드 버그 탐색 계약 검증 추가"
```

Expected: executable validator 한 파일만 포함한 커밋이 생성된다.

---

### Task 2: Backend 한글 HTML 보고서 템플릿 추가

**Files:**
- Create: `docs/bug-reports/backend-report-template.html`
- Test: `.codex/agents/tests/validate-backend-bug-hunter.sh`

**Interfaces:**
- Consumes: target 계약, scenario 결과, ticket, 두 clean run의 정제 evidence, partial state
- Produces: 외부 resource 없이 로컬에서 열리는 backend 전용 한글 HTML 보고서

- [ ] **Step 1: 전용 보고서 템플릿을 작성한다**

Create `docs/bug-reports/backend-report-template.html` with:

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="backend-bug-hunter-isolation" content="run-specific">
  <title>__REPORT_TITLE__</title>
  <style>
    :root { color-scheme:light; font-family:system-ui,sans-serif; background:#f3f5f7; color:#20262d; }
    * { box-sizing:border-box; } body { margin:0; } a { color:#245ea8; }
    .page { width:min(1180px,calc(100% - 2rem)); margin:auto; padding:2rem 0 4rem; }
    .hero,.panel,.bug-card,.run-evidence { background:#fff; border:1px solid #cfd7df; border-radius:.8rem; padding:1.25rem; }
    .panel,.bug-card,.run-evidence { margin-top:1rem; } .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(12rem,1fr)); gap:.8rem; }
    .metric { background:#eef3f8; border-radius:.6rem; padding:1rem; } .metric strong { display:block; font-size:1.6rem; }
    .severity { display:inline-block; border:1px solid currentColor; border-radius:999px; padding:.25rem .6rem; font-weight:800; }
    .severity-blocking,.severity-high { color:#a22520; } .severity-medium { color:#7a5700; } .severity-low { color:#236246; }
    code,pre { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; } pre { white-space:pre-wrap; overflow-wrap:anywhere; background:#111820; color:#f7fafc; padding:1rem; border-radius:.55rem; }
    table { width:100%; border-collapse:collapse; } th,td { padding:.65rem; border:1px solid #cfd7df; text-align:left; vertical-align:top; }
    dt { margin-top:.75rem; font-weight:800; } dd { margin:.25rem 0 0; } :focus-visible { outline:3px solid #246fca; outline-offset:3px; }
    @media print { :root { background:#fff; } .page { width:100%; padding:0; } .hero,.panel,.bug-card,.run-evidence { break-inside:avoid; box-shadow:none; } }
  </style>
</head>
<body>
<main class="page">
  <header class="hero"><p>Backend 버그 탐색 보고서</p><h1>__REPORT_TITLE__</h1><p>생성 시각: <time datetime="__GENERATED_AT_ISO__">__GENERATED_AT_KO__</time></p></header>
  <section class="panel"><h2>탐색 범위</h2><p>__SCOPE_DESCRIPTION__</p><h3>제외 범위</h3><p>__EXCLUDED_SCOPE__</p></section>
  <section class="panel"><h2>실행 계약</h2><dl><dt>대상</dt><dd><code>__TARGET_IDENTIFIER__</code></dd><dt>Entry point</dt><dd><code>__ENTRY_POINT__</code></dd><dt>OpenAPI baseline</dt><dd><code>__OPENAPI_BASELINE_OR_NA__</code></dd><dt>Domain contract</dt><dd><code>__DOMAIN_CONTRACT__</code></dd><dt>Revision</dt><dd><code>__REVISION__</code></dd></dl></section>
  <section class="panel"><h2>격리 환경</h2><dl><dt>시작 fixture</dt><dd>__STARTING_FIXTURE__</dd><dt>인증 상태</dt><dd>__AUTH_STATE__</dd><dt>임시 DB·파일</dt><dd><code>__SANITIZED_TEMP_PATH__</code></dd><dt>격리·초기화</dt><dd>__ISOLATION_METHOD__</dd><dt>정리 방식</dt><dd>__CLEANUP_METHOD__</dd></dl></section>
  <section class="panel"><h2>시나리오 결과</h2><table><thead><tr><th>분류</th><th>결과</th><th>근거 또는 비적용 사유</th></tr></thead><tbody>__SCENARIO_ROWS__</tbody></table></section>
  <section class="panel"><h2>결과 요약</h2><div class="grid"><div class="metric">확정<strong>__CONFIRMED_COUNT__</strong></div><div class="metric">등록<strong>__REGISTERED_COUNT__</strong></div><div class="metric">중복<strong>__DUPLICATE_COUNT__</strong></div><div class="metric">제외<strong>__EXCLUDED_COUNT__</strong></div></div></section>
  <section class="panel"><h2>등록한 버그</h2>
    <article class="bug-card" id="bug-001"><p><span class="severity severity-__BUG_SEVERITY_CLASS__">심각도 __BUG_SEVERITY__</span></p><h3>__BUG_TITLE__</h3>
      <dl><dt>티켓</dt><dd><code>#__TICKET_ID__</code> · <code>__REGISTRATION_COMMAND__</code> · <code>__TICKET_STATUS__</code></dd><dt>기대 결과</dt><dd>__EXPECTED_RESULT__</dd><dt>실제 결과</dt><dd>__ACTUAL_RESULT__</dd><dt>영향</dt><dd>__IMPACT__</dd><dt>근거 계약</dt><dd>__AUTHORITATIVE_REQUIREMENT__</dd></dl>
      <section class="run-evidence" data-run="1"><h4>Clean run 1</h4><dl><dt>정제된 요청</dt><dd><pre>__SANITIZED_REQUEST__</pre></dd><dt>정제된 응답</dt><dd><pre>__SANITIZED_RESPONSE__</pre></dd><dt>정제 로그</dt><dd><pre>__SANITIZED_LOGS__</pre></dd><dt>저장 전 상태</dt><dd><pre>__STORAGE_BEFORE__</pre></dd><dt>저장 후 상태</dt><dd><pre>__STORAGE_AFTER__</pre></dd></dl></section>
      <section class="run-evidence" data-run="2"><h4>Clean run 2</h4><dl><dt>정제된 요청</dt><dd><pre>__SANITIZED_REQUEST_RUN_2__</pre></dd><dt>정제된 응답</dt><dd><pre>__SANITIZED_RESPONSE_RUN_2__</pre></dd><dt>정제 로그</dt><dd><pre>__SANITIZED_LOGS_RUN_2__</pre></dd><dt>저장 전 상태</dt><dd><pre>__STORAGE_BEFORE_RUN_2__</pre></dd><dt>저장 후 상태</dt><dd><pre>__STORAGE_AFTER_RUN_2__</pre></dd></dl></section>
    </article>
  </section>
  <section class="panel"><h2>중복된 관찰</h2><p>__DUPLICATE_OBSERVATIONS__</p></section>
  <section class="panel"><h2>제외한 관찰</h2><p>__EXCLUDED_OBSERVATIONS__</p></section>
  <section class="panel"><h2>수행한 검사</h2><ul>__CHECK_RESULTS__</ul></section>
  <section class="panel"><h2>실패 및 부분 완료</h2><p>__PARTIAL_STATE__</p><p>정리 결과: __CLEANUP_RESULT__</p></section>
  <section class="panel"><h2>제약 및 미확인 항목</h2><p>__LIMITATIONS__</p></section>
</main>
</body>
</html>
```

- [ ] **Step 2: validator의 다음 실패를 확인한다**

Run:

```sh
mise exec -- bash .codex/agents/tests/validate-backend-bug-hunter.sh
```

Expected: template 검사는 통과하고 FAIL with `missing .../.codex/agents/backend-bug-hunter.toml`.

- [ ] **Step 3: 템플릿만 커밋한다**

```sh
git add -- docs/bug-reports/backend-report-template.html
git commit -m "백엔드 버그 보고서 템플릿 추가"
```

Expected: template 한 파일만 포함한 커밋이 생성된다.

---

### Task 3: `backend-bug-hunter` custom agent 추가

**Files:**
- Create: `.codex/agents/backend-bug-hunter.toml`
- Test: `.codex/agents/tests/validate-backend-bug-hunter.sh`
- Reference: `.codex/agents/bug-hunter.toml`
- Reference: `.codex/agents/backend-review.toml`
- Reference: `backend/AGENTS.md`

**Interfaces:**
- Consumes: 하나의 target과 entry point, 조건부 OpenAPI baseline, domain contract, fixture·인증·격리·명령·제외·mutation·failure 입력
- Produces: 두 clean run 증거, 신규 ticket, 한글 HTML 보고서 또는 정확한 partial handoff

- [ ] **Step 1: agent 정의를 작성한다**

Create `.codex/agents/backend-bug-hunter.toml` with:

```toml
name = "backend-bug-hunter"
description = "Use to explore exactly one assigned backend operationId or explicit backend use case in isolated fixtures, register confirmed non-duplicate defects, and write a Korean HTML report."
sandbox_mode = "workspace-write"
model_reasoning_effort = "high"

developer_instructions = """
Act as the Romance Agent project's backend defect hunter. Execute and explore exactly one operationId or one explicit backend use case assigned by the main agent. Discover and reproduce observable defects; do not review a completed implementation, browse UI, implement fixes, or approve a feature.

Required inputs are: the exact target kind and identifier; its backend entry point; the main-agent-approved OpenAPI baseline and matching operationId when the target is consumer-facing; relevant domain contracts and acceptance criteria; starting fixture and authentication state; run-specific temporary database and file paths plus their approved parent, isolation and cleanup method; allowed commands; excluded scope; data-mutation limits; and assigned error, concurrency, and retry scenarios. Stop before setup when any applicable input is missing, when more than one target is assigned, when the boundary is ambiguous, or when isolation cannot be proven. A backend use case with no consumer-facing operation does not require an OpenAPI artifact; record that as not applicable.

Read the root AGENTS.md, backend/README.md, backend/AGENTS.md, backend/docs/backend-coding-rules.md, relevant domain contracts, acceptance criteria, and the exact approved OpenAPI baseline when applicable. Use CodeGraph first when .codegraph/ exists. Record the Git revision and pre-existing changes. Do not modify product code or tests. Do not modify docs/api/openapi.yaml or docs/domains/. Do not modify .codex/agents/bug-hunter.toml or .codex/agents/backend-review.toml. Do not modify backend/AGENTS.md, package files, lockfiles, or pre-existing documentation.

Before backend setup, run zellij-agent ticket-worker list --json and retain the result as the duplicate baseline. Run ticket-worker init once only if the list command explicitly reports that the queue is uninitialized. Never edit the ticket database.

Never use actual production data, an external provider, a shared database, or files shared with another run. Resolve every assigned temporary path and verify that it is under the approved temporary parent and different from production or shared paths. Create a unique directory per run. Build each run from the immutable starting fixture or its deterministic generator. Do not share database, lock, journal, replacement-file, or provider-stub state between runs. Clean up only paths owned by the current run; never delete a repository root, user home, broad glob, unresolved environment-variable target, fixture source, or tracked file. Record cleanup results and leftovers.

Use fake, stub, or assigned failure adapters instead of network providers or real credentials. Verify the normal path first, then the reachable boundary and validation cases. For an HTTP operation, inspect the applicable normal, boundary, validation, 404, 409, 422, and 500 behavior from the approved contract. For a non-HTTP use case, inspect the corresponding typed domain or application failures. Also inspect persistence rollback, concurrency, retry, provider failure, and sensitive log exposure when they are reachable and in scope. Do not force unreachable cases; report each non-applicable scenario and the reason.

For every suspected defect, record the authoritative expectation, minimal trigger, observable result, impact, request and response or use-case input/result, sanitized logs, storage state before and after, fixture identity, command, exit status, and sanitized temporary-path identity. Replace Authorization values, cookies, session identifiers, tokens, credentials, provider secrets, private keys, environment secrets, and private manuscript or character content with [REDACTED]. Do not persist raw database dumps, SQLite journals, binary payloads, complete snapshots, full environment output, or secret-bearing stack traces. Limit persistence evidence to the minimum relevant records, revisions, row counts, hashes, file presence, and sanitized diffs.

Confirm a defect only when the same observable failure reproduces twice from independent clean states. Reset from the immutable fixture into a new unique run directory before the second attempt. Do not count retrying against state left by the first run as a clean reproduction.

Immediately before registration, run zellij-agent ticket-worker list --json again. Compare target, trigger, observable failure, impact, and repair boundary. Register only confirmed, in-scope, authoritative, independently repairable defects that are not duplicates. Do not register preferences, feature ideas, invisible style concerns, unreproduced behavior, ambiguous product decisions, or observations requiring forbidden resources.

Classify each registrable defect as Blocking, High, Medium, or Low and reserve its report #bug-NNN anchor first. For Blocking, High, and Medium, create one Korean bug-specific design document and one implementation-ready plan that both link relatively to the report and exact anchor, self-review them, and use zellij-agent ticket-worker add. For Low, create no design or plan; use zellij-agent ticket-worker fast-add with the report path and exact anchor as evidence and include the exact prompt instruction FAST 모드로 처리한다. Every prompt must require feature-development, skip brainstorming and writing-plans, and prohibit work outside the defect scope. Query fresh JSON after registration and verify the command, ID, title, summary, prompt, evidence paths, and returned status. Never edit the ticket database or guess a retry after duplicate, registration, or verification failure.

Write one Korean report at docs/bug-reports/YYYY-MM-DD-HHmm-backend-<scope-slug>.html using docs/bug-reports/backend-report-template.html. Keep lang="ko", UTF-8, the run-specific isolation marker, inline CSS, semantic headings, visible focus, print styles, stable bug anchors, and no script, CDN, external resources, or unresolved tokens. Include scope, execution contract, fixture and authentication, temporary database and file paths in sanitized form, isolation and cleanup, every scenario result or non-applicable reason, tickets, duplicates, exclusions, commands, limitations, and for each defect both clean runs' request and response, sanitized logs, and storage state before and after. If no defect qualifies, state only that this bounded exploration found no registrable confirmed defect; do not generalize to the backend.

Owned writes are limited to the new backend report and evidence assets, new bug-specific specs and plans required by severity, ticket-worker commands, and the assigned run-specific temporary paths. Do not stage, commit, restore, overwrite, rename, or delete pre-existing changes. Commit only the new bug documents, report, and evidence assets with exact pathspecs. Never commit temporary fixtures, databases, credentials, or raw logs.

On any failure, stop dependent steps and return a partial handoff. State the target, failed phase, completed and unexecuted phases, commands and exit statuses, sanitized error, created and validated artifacts, commits, ticket IDs and verification status, run-specific temporary paths, cleanup success or leftovers, preserved product and pre-existing files, limitations, and the exact condition needed to resume. If ticket registration succeeded before a later failure, report the real ticket and status. Never claim a run, reproduction, cleanup, artifact, registration, or validation that fresh evidence does not prove.

Return a Korean handoff containing: target and entry point; OpenAPI baseline and operationId or explicit non-applicability; domain sources; fixture, authentication and isolation; scenarios and results; confirmed defects with two-run evidence; tickets and severity; duplicates and exclusions; report and document paths; commands and validation; cleanup; partial state or limitations; commits; and preserved changes. The main agent reviews all tickets and artifacts and alone decides implementation and completion.
"""
```

- [ ] **Step 2: agent 구조와 browser 도구 부재를 독립 확인한다**

Run:

```sh
mise exec -- python - <<'PY'
from pathlib import Path
import tomllib

data = tomllib.loads(Path('.codex/agents/backend-bug-hunter.toml').read_text())
assert data['name'] == 'backend-bug-hunter'
assert data['sandbox_mode'] == 'workspace-write'
assert data['model_reasoning_effort'] == 'high'
assert 'mcp_servers' not in data
print('backend-bug-hunter TOML structure: PASS')
PY
```

Expected: `backend-bug-hunter TOML structure: PASS`.

- [ ] **Step 3: validator가 루트 정책에서만 실패하는지 확인한다**

Run:

```sh
mise exec -- bash .codex/agents/tests/validate-backend-bug-hunter.sh
```

Expected: agent와 template fixture 검사는 통과하고 FAIL because `## Backend Bug-Hunting Subagent` is absent from `AGENTS.md`.

- [ ] **Step 4: agent만 커밋한다**

```sh
git add -- .codex/agents/backend-bug-hunter.toml
git commit -m "백엔드 버그 탐색 에이전트 추가"
```

Expected: agent TOML 한 파일만 포함한 커밋이 생성된다.

---

### Task 4: 루트 위임·소유권·실패 정책 동기화

**Files:**
- Modify: `AGENTS.md` immediately after `## Browser Bug-Hunting Subagent`
- Test: `.codex/agents/tests/validate-backend-bug-hunter.sh`
- Verify unchanged: `.codex/agents/bug-hunter.toml`
- Verify unchanged: `.codex/agents/backend-review.toml`
- Verify unchanged: `backend/AGENTS.md`

**Interfaces:**
- Consumes: main-agent assignment and backend-bug-hunter handoff
- Produces: repository-wide dispatch gate, ownership, duplicate/registration, evidence and failure policy

- [ ] **Step 1: browser section을 수정하지 않고 독립 backend section을 추가한다**

Insert the following section after the complete existing `## Browser Bug-Hunting Subagent` section and before `## Shared Contracts and Domain Boundaries`:

```markdown
## Backend Bug-Hunting Subagent

When the user requests defect discovery for a bounded backend operation or use
case, use the project-scoped `backend-bug-hunter` agent defined in
`.codex/agents/backend-bug-hunter.toml`. Assign exactly one `operationId` or one
explicit backend use case. Do not dispatch it as an implementation review, a
browser audit, an application-wide backend audit, or while another agent is
modifying the same operation or use-case boundary.

Every assignment must state the target and backend entry point; the exact
main-approved OpenAPI baseline and matching `operationId` when consumer-facing;
relevant domain contracts and acceptance criteria; starting fixture and
authentication state; run-specific temporary database and file paths, approved
temporary parent, isolation, reset, and cleanup method; allowed commands;
excluded scope; data-mutation limits; and error, concurrency, and retry
scenarios. Missing applicable input, multiple targets, an ambiguous boundary,
or unproven storage isolation stops setup. A non-HTTP use case does not require
an OpenAPI artifact.

The `backend-bug-hunter` owns bounded execution, applicable normal and failure
scenario exploration, two independent clean-state reproductions, duplicate
checks, severity classification, direct ticket registration, and one Korean
HTML report under `docs/bug-reports/`. It may create bug-specific specs and
plans only when required by severity. It does not implement fixes, review a
completed implementation, or approve features.

Use only immutable or deterministically generated fixtures copied into a unique
temporary directory for each run. Never use actual production data, external
providers, shared databases, shared files, real credentials, or state left by
another run. Resolve and validate temporary paths beneath the assignment's
approved parent before setup. Clean only paths owned by the current run and
report cleanup failures or leftovers.

Check the normal path and applicable boundary, validation, 404, 409, 422, 500,
persistence rollback, concurrency, retry, provider-failure, and sensitive-log
scenarios. Use fake or stub providers. Record a reason for every non-applicable
scenario instead of forcing an unreachable failure.

Before setup, run `zellij-agent ticket-worker list --json`; run
`zellij-agent ticket-worker init` once only when the list command explicitly
reports that the queue is uninitialized. Immediately before registration, query
fresh JSON again and compare target, trigger, observable failure, impact, and
repair boundary. Register only authoritative, independently repairable defects
that reproduced twice from independent clean states and are not duplicates.
Never edit the ticket database to recover from a duplicate or registration
failure.

Reserve an HTML `#bug-NNN` anchor for every registrable defect. For `Blocking`,
`High`, and `Medium`, create and self-review one Korean bug design and one
implementation-ready plan, link both documents to the exact report anchor, and
register with `zellij-agent ticket-worker add`. For `Low`, create no design or
plan and use `zellij-agent ticket-worker fast-add` with the report path and
anchor as evidence; its prompt must include `FAST 모드로 처리한다`. Every prompt
requires `feature-development`, skips `brainstorming` and `writing-plans`, and
prohibits changes outside the defect scope. Query fresh JSON after registration
and verify the command and every registered value.

The Korean report uses `docs/bug-reports/backend-report-template.html` and
records the target contract, fixture, authentication, temporary paths and
isolation, scenario results, tickets, duplicates, exclusions, commands,
cleanup, and limitations. For each defect include both clean runs' request and
response, sanitized logs, and storage state before and after. Redact
authorization, cookies, tokens, credentials, provider secrets, private keys,
environment secrets, and private manuscript or character content. Do not store
raw database dumps, journals, complete snapshots, binary payloads, or
secret-bearing stack traces.

Owned writes are limited to new backend bug reports and evidence, severity-
required new bug specs and plans, ticket-worker commands, and assigned
run-specific temporary paths. Product code and tests, OpenAPI, domain contracts,
package files, lockfiles, `backend/AGENTS.md`, existing agent definitions, and
pre-existing files are read-only. Commit only newly created bug documents,
reports, and evidence with exact pathspecs; never commit temporary data.

On failure, stop dependent work and return a partial handoff with the target,
failed phase, completed and unexecuted phases, commands and exits, sanitized
error, artifacts and validation state, ticket IDs and verified status,
temporary paths, cleanup result, preserved files, limitations, and the exact
resume condition. Never claim work not proven by fresh evidence. The main agent
reviews the report and every ticket before assigning implementation and retains
integration, review, and final-verification responsibility.
```

- [ ] **Step 2: 전용 validator 전체 통과를 확인한다**

Run:

```sh
mise exec -- bash .codex/agents/tests/validate-backend-bug-hunter.sh
```

Expected:

```text
backend report fixtures passed: 3 positive, 8 negative
backend-bug-hunter configuration, policy, isolation, redaction, and report contract are valid
```

- [ ] **Step 3: 기존 역할과 계약이 변경되지 않았는지 확인한다**

Run:

```sh
git diff --exit-code 333f417 -- \
  .codex/agents/bug-hunter.toml \
  .codex/agents/backend-review.toml \
  backend/AGENTS.md \
  docs/api/openapi.yaml \
  docs/domains
```

Expected: exit `0`, no output.

- [ ] **Step 4: 루트 정책만 커밋한다**

```sh
git add -- AGENTS.md
git commit -m "백엔드 버그 탐색 정책 추가"
```

Expected: `AGENTS.md` 한 파일만 포함한 커밋이 생성된다.

---

### Task 5: 통합 검증과 main-thread review

**Files:**
- Verify: `.codex/agents/backend-bug-hunter.toml`
- Verify: `.codex/agents/tests/validate-backend-bug-hunter.sh`
- Verify: `docs/bug-reports/backend-report-template.html`
- Verify: `AGENTS.md`
- Verify unchanged: `.codex/agents/bug-hunter.toml`
- Verify unchanged: `.codex/agents/backend-review.toml`
- Verify unchanged: `backend/AGENTS.md`

**Interfaces:**
- Consumes: Tasks 1–4의 커밋과 승인된 설계
- Produces: 요구사항 추적성, 검증 결과, 알려진 선행 실패와 통합 위험을 포함한 최종 handoff

- [ ] **Step 1: 계획·설계·구현 추적성을 검토한다**

Run:

```sh
rg -n "operationId|entry point|OpenAPI baseline|domain contracts|starting fixture|authentication state|temporary database|allowed commands|excluded scope|data-mutation|concurrency|retry|rollback|provider failure|sensitive log|partial handoff" \
  .codex/agents/backend-bug-hunter.toml AGENTS.md
```

Expected: 설계의 필수 입력, 시나리오, 안전과 실패 계약이 agent와 루트 정책 양쪽에서 확인된다.

- [ ] **Step 2: 정적·HTML·격리·redaction 검증을 다시 실행한다**

Run:

```sh
mise exec -- bash .codex/agents/tests/validate-backend-bug-hunter.sh
git diff --check 333f417..HEAD
```

Expected: validator의 `3 positive, 8 negative`와 최종 PASS가 출력되고 whitespace error가 없다.

- [ ] **Step 3: 기존 browser validator의 선행 상태를 재확인한다**

Run:

```sh
mise exec -- bash .codex/agents/tests/validate-bug-hunter.sh
```

Expected baseline result: FAIL with `missing instruction: zellij-agent ticket-worker list --json`. 이 실패가 여전히 HEAD 기준 기존 `bug-hunter.toml` 계약에서 발생하며 이번 diff가 해당 파일을 변경하지 않았음을 기록한다. 다른 위치에서 실패하면 새 회귀로 조사한다.

- [ ] **Step 4: 변경 경계와 worktree를 최종 확인한다**

Run:

```sh
git diff --stat 333f417..HEAD
git diff --name-status 333f417..HEAD
git diff --exit-code 333f417 -- \
  .codex/agents/bug-hunter.toml \
  .codex/agents/backend-review.toml \
  backend/AGENTS.md \
  docs/api/openapi.yaml \
  docs/domains
git status --short --branch
```

Expected: 승인된 spec·plan, 새 agent·validator·template와 루트 `AGENTS.md`만 변경되고 worktree가 clean이다.

- [ ] **Step 5: main-thread review를 수행한다**

승인된 설계의 수용 기준 1–8을 각 파일과 validator evidence에 매핑한다. 특히 다음을 수동 확인한다.

- `backend-review`의 read-only implementation review 문구가 새 agent에 복사되지 않았다.
- browser route, viewport, Playwright 또는 screenshot을 새 agent가 요구하지 않는다.
- operation 대상만 OpenAPI baseline을 요구하고 non-HTTP use case는 명시적으로 비적용 가능하다.
- 두 clean run은 서로 다른 고유 저장소에서 시작한다.
- duplicate query가 setup 전과 registration 직전 두 번 존재한다.
- report에는 request/response, sanitized logs, before/after storage가 두 run 모두 존재한다.
- partial handoff가 ticket 등록 후 실패와 cleanup 실패도 숨기지 않는다.
- primary checkout의 미커밋 `AGENTS.md`와 `bug-hunter.toml` 변경을 가져오거나 덮어쓰지 않았다.

Expected: accepted finding이 없거나, 발견한 모든 finding을 이 task 범위 안에서 수정하고 Step 2–4를 다시 실행한다. 이 agent configuration/policy 변경을 `backend-review`에 배정하지 않는다. 그러면 기존 reviewer의 제품 operation 검토 책임이 혼합된다.

- [ ] **Step 6: ticket #25 완료 전 최종 상태를 기록한다**

Run:

```sh
zellij-agent ticket-worker list --json
git log --oneline 333f417..HEAD
```

Expected: ticket `25`가 현재 실행 대상임을 확인하고, 설계·계획·구현 커밋과 검증 결과를 최종 보고에 사용할 수 있다. 모든 구현과 검증이 끝난 뒤에만 ticket workflow의 완료 처리를 수행한다.
