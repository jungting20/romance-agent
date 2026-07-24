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
