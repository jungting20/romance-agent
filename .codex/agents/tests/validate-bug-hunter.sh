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
