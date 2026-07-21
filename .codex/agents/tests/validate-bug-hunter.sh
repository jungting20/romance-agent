#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../../.." && pwd -P)

python3 - "$repo_root" <<'PY'
import pathlib
import re
import sys
import tomllib
from html.parser import HTMLParser

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

reverse_link_instruction = (
    "Before committing them, ensure both the design document and implementation "
    "plan contain a relative link to the reserved HTML report path with its "
    "exact '#bug-NNN' anchor."
)
assert reverse_link_instruction in instructions, "missing bidirectional report traceability instruction"

playwright = agent["mcp_servers"]["playwright-test"]
assert playwright["command"] == "mise"
assert playwright["args"] == [
    "exec", "--", "pnpm", "--dir", "frontend", "exec", "playwright",
    "run-test-mcp-server", "--config", "playwright.config.ts",
]
expected_tools = {
    "planner_setup_page", "browser_click", "browser_close",
    "browser_console_messages", "browser_drag", "browser_evaluate",
    "browser_file_upload", "browser_handle_dialog", "browser_hover",
    "browser_navigate", "browser_navigate_back", "browser_network_request",
    "browser_network_requests", "browser_press_key", "browser_select_option",
    "browser_snapshot", "browser_take_screenshot", "browser_type",
    "browser_wait_for",
}
assert set(playwright["enabled_tools"]) == expected_tools, "enabled-tool allowlist changed"

required_headings = {
    "탐색 범위", "실행 환경", "결과 요약", "등록한 버그",
    "중복된 관찰", "제외한 관찰", "수행한 검사", "제약 및 미확인 항목",
}


class ReportInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.html_lang = None
        self.has_utf8 = False
        self.has_viewport = False
        self.has_script = False
        self.external_resources = []
        self.headings = []
        self.bug_cards = []
        self._heading_parts = None
        self._card = None
        self._link = None
        self._caption_parts = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.html_lang = attrs.get("lang")
        elif tag == "meta":
            self.has_utf8 |= attrs.get("charset", "").lower() == "utf-8"
            self.has_viewport |= attrs.get("name", "").lower() == "viewport" and bool(attrs.get("content", "").strip())
        elif tag == "script":
            self.has_script = True
        elif tag == "h2":
            self._heading_parts = []
        elif tag == "article" and "bug-card" in attrs.get("class", "").split():
            self._card = {"id": attrs.get("id"), "links": [], "alts": [], "captions": []}
            self.bug_cards.append(self._card)
        elif tag == "a" and self._card is not None:
            self._link = {"href": attrs.get("href", ""), "text": []}
            self._card["links"].append(self._link)
        elif tag == "img" and self._card is not None:
            self._card["alts"].append(attrs.get("alt", ""))
        elif tag == "figcaption" and self._card is not None:
            self._caption_parts = []

        for attr in ("src", "href", "poster"):
            value = attrs.get(attr, "")
            if re.match(r"https?://", value, re.IGNORECASE):
                self.external_resources.append(value)

    def handle_endtag(self, tag):
        if tag == "h2" and self._heading_parts is not None:
            self.headings.append("".join(self._heading_parts).strip())
            self._heading_parts = None
        elif tag == "a":
            self._link = None
        elif tag == "figcaption" and self._caption_parts is not None:
            self._card["captions"].append("".join(self._caption_parts).strip())
            self._caption_parts = None
        elif tag == "article":
            self._card = None

    def handle_data(self, data):
        if self._heading_parts is not None:
            self._heading_parts.append(data)
        if self._link is not None:
            self._link["text"].append(data)
        if self._caption_parts is not None:
            self._caption_parts.append(data)


def inspect_report(path, *, generated):
    html = path.read_text(encoding="utf-8")
    inspector = ReportInspector()
    inspector.feed(html)
    assert inspector.html_lang == "ko", f'{path}: missing lang="ko"'
    assert inspector.has_utf8, f"{path}: missing UTF-8 charset"
    assert inspector.has_viewport, f"{path}: missing viewport metadata"
    assert not inspector.has_script, f"{path}: script is forbidden"
    assert not inspector.external_resources, f"{path}: external HTTP(S) resource"
    assert not re.search(r"url\(\s*['\"]?https?://", html, re.IGNORECASE), f"{path}: external CSS resource"
    missing_headings = required_headings - set(inspector.headings)
    assert not missing_headings, f"{path}: missing headings: {sorted(missing_headings)}"

    if not generated:
        return

    assert not re.search(r"__[A-Z0-9_]+__", html), f"{path}: unresolved token"
    if not inspector.bug_cards:
        assert re.search(r"확정(?:된)?\s*버그(?:가)?\s*없", html), f"{path}: missing Korean zero-result marker"
        return

    anchors = [card["id"] for card in inspector.bug_cards]
    assert all(re.fullmatch(r"bug-\d{3}", anchor or "") for anchor in anchors), f"{path}: unstable bug anchor"
    assert len(anchors) == len(set(anchors)), f"{path}: duplicate bug anchor"
    for card in inspector.bug_cards:
        links = {"".join(link["text"]).strip(): link["href"] for link in card["links"]}
        for label in ("설계", "구현 계획"):
            href = links.get(label, "")
            assert href and not href.startswith(("/", "#")), f"{path}: {card['id']} {label} link is not relative"
            assert not re.match(r"https?://", href, re.IGNORECASE), f"{path}: {card['id']} {label} link is external"
            assert href.split("#", 1)[0].endswith(".md"), f"{path}: {card['id']} {label} link is not Markdown"
        assert card["alts"] and all(alt.strip() for alt in card["alts"]), f"{path}: {card['id']} empty screenshot alt"
        assert all(not re.fullmatch(r"(?:todo|placeholder|screenshot)", alt.strip(), re.IGNORECASE) for alt in card["alts"]), f"{path}: {card['id']} placeholder screenshot alt"
        assert card["captions"] and all(caption.strip() for caption in card["captions"]), f"{path}: {card['id']} empty screenshot caption"
        assert all(not re.fullmatch(r"(?:todo|placeholder|caption)", caption.strip(), re.IGNORECASE) for caption in card["captions"]), f"{path}: {card['id']} placeholder screenshot caption"

inspect_report(template_path, generated=False)

agents_md = (root / "AGENTS.md").read_text(encoding="utf-8")
assert "## Browser Bug-Hunting Subagent" in agents_md
normalized_agents_md = re.sub(r"\s+", " ", agents_md)
for phrase in [
    "bug-hunter", "target route", "user flow", "starting state",
    "authentication state", "viewport", "allowed server and verification commands",
    "excluded actions", "data-mutation limits",
]:
    assert phrase in normalized_agents_md, f"missing delegation field: {phrase}"

for report_path in sorted((root / "docs/bug-reports").glob("*.html")):
    if report_path.name == "report-template.html":
        continue
    inspect_report(report_path, generated=True)

print("bug-hunter configuration and report contract are valid")
PY
