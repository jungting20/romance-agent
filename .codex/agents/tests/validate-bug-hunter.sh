#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$0")/../../.." && pwd -P)

python3 - "$repo_root" <<'PY'
import pathlib
import re
import sys
import tomllib
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

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
url_attributes = {
    "action", "archive", "background", "cite", "classid", "codebase",
    "data", "formaction", "href", "longdesc", "manifest", "ping", "poster",
    "profile", "src", "srcset", "usemap",
}


def attribute_urls(name, value):
    if name == "srcset":
        return [candidate.strip().split()[0] for candidate in value.split(",") if candidate.strip()]
    if name == "ping":
        return value.split()
    return [value]


def is_external_url(value):
    value = value.strip()
    if not value:
        return False
    parsed = urlsplit(value)
    return bool(parsed.scheme or parsed.netloc) or value.startswith("//")


def external_css_urls(css):
    references = [
        match.group(2).strip()
        for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", css, re.IGNORECASE | re.DOTALL)
    ]
    references.extend(
        match.group(2).strip()
        for match in re.finditer(r"@import\s+(?!url\()(['\"])(.*?)\1", css, re.IGNORECASE | re.DOTALL)
    )
    references.extend(
        match.group(1).strip()
        for match in re.finditer(r"@import\s+(?!url\()([^'\"\s;)]+)", css, re.IGNORECASE)
    )
    return [reference for reference in references if is_external_url(reference)]


class ReportInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.html_lang = None
        self.has_utf8 = False
        self.has_viewport = False
        self.has_script = False
        self.external_resources = []
        self.css_chunks = []
        self.headings = []
        self.bug_cards = []
        self._heading_parts = None
        self._card = None
        self._link = None
        self._caption_parts = None
        self._in_style = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.html_lang = attrs.get("lang")
        elif tag == "meta":
            self.has_utf8 |= attrs.get("charset", "").lower() == "utf-8"
            self.has_viewport |= attrs.get("name", "").lower() == "viewport" and bool(attrs.get("content", "").strip())
        elif tag == "script":
            self.has_script = True
        elif tag == "style":
            self._in_style = True
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

        if "style" in attrs:
            self.css_chunks.append(attrs["style"])
        for attr, value in attrs.items():
            if attr in url_attributes:
                for candidate in attribute_urls(attr, value or ""):
                    if is_external_url(candidate):
                        self.external_resources.append((attr, candidate))

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
        elif tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if self._heading_parts is not None:
            self._heading_parts.append(data)
        if self._link is not None:
            self._link["text"].append(data)
        if self._caption_parts is not None:
            self._caption_parts.append(data)
        if self._in_style:
            self.css_chunks.append(data)


def validate_report_html(html, *, source, generated):
    inspector = ReportInspector()
    inspector.feed(html)
    assert inspector.html_lang == "ko", f'{source}: missing lang="ko"'
    assert inspector.has_utf8, f"{source}: missing UTF-8 charset"
    assert inspector.has_viewport, f"{source}: missing viewport metadata"
    assert not inspector.has_script, f"{source}: script is forbidden"
    assert not inspector.external_resources, f"{source}: external resource: {inspector.external_resources}"
    css_external = [url for css in inspector.css_chunks for url in external_css_urls(css)]
    assert not css_external, f"{source}: external CSS resource: {css_external}"
    missing_headings = required_headings - set(inspector.headings)
    assert not missing_headings, f"{source}: missing headings: {sorted(missing_headings)}"

    if not generated:
        assert 'id="bug-001"' in html, f"{source}: missing template bug anchor"
        assert 'alt="__BUG_SCREENSHOT_ALT__"' in html, f"{source}: missing template screenshot alt token"
        return

    assert not re.search(r"__[A-Z0-9_]+__", html), f"{source}: unresolved token"
    if not inspector.bug_cards:
        assert re.search(r"확정(?:된)?\s*버그(?:가)?\s*없", html), f"{source}: missing Korean zero-result marker"
        return

    anchors = [card["id"] for card in inspector.bug_cards]
    assert all(re.fullmatch(r"bug-\d{3}", anchor or "") for anchor in anchors), f"{source}: unstable bug anchor"
    assert len(anchors) == len(set(anchors)), f"{source}: duplicate bug anchor"
    for card in inspector.bug_cards:
        links = {"".join(link["text"]).strip(): link["href"] for link in card["links"]}
        for label in ("설계", "구현 계획"):
            href = links.get(label, "")
            parsed = urlsplit(href.strip())
            decoded_path = unquote(parsed.path)
            is_relative = bool(href and decoded_path) and not (
                parsed.scheme or parsed.netloc or decoded_path.startswith(("/", "\\"))
            )
            assert is_relative, f"{source}: {card['id']} {label} link is not relative"
            assert decoded_path.lower().endswith(".md"), f"{source}: {card['id']} {label} link is not Markdown"
        assert card["alts"] and all(alt.strip() for alt in card["alts"]), f"{source}: {card['id']} empty screenshot alt"
        assert all(not re.fullmatch(r"(?:todo|placeholder|screenshot)", alt.strip(), re.IGNORECASE) for alt in card["alts"]), f"{source}: {card['id']} placeholder screenshot alt"
        assert card["captions"] and all(caption.strip() for caption in card["captions"]), f"{source}: {card['id']} empty screenshot caption"
        assert all(not re.fullmatch(r"(?:todo|placeholder|caption)", caption.strip(), re.IGNORECASE) for caption in card["captions"]), f"{source}: {card['id']} placeholder screenshot caption"


def inspect_report(path, *, generated):
    validate_report_html(
        path.read_text(encoding="utf-8"),
        source=str(path),
        generated=generated,
    )

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


fixture_sections = "".join(f"<section><h2>{heading}</h2></section>" for heading in sorted(required_headings))
valid_fixture = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<style>.local {{ background-image: url('./paper.png'); }}</style></head><body>
{fixture_sections}
<article class="bug-card" id="bug-001">
<a href="../superpowers/specs/bug-001.md">설계</a>
<a href="../superpowers/plans/bug-001.md">구현 계획</a>
<figure><img srcset="./shot.png 1x, ./shot@2x.png 2x" src="./shot.png" alt="저장 버튼 오류 화면">
<figcaption>저장 버튼을 누른 뒤 오류가 표시된 화면</figcaption></figure>
</article></body></html>"""
zero_fixture = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body>{fixture_sections}<p>확정된 버그가 없습니다.</p></body></html>"""


def assert_fixture_rejected(name, html, expected_message):
    try:
        validate_report_html(html, source=f"fixture:{name}", generated=True)
    except AssertionError as error:
        assert expected_message in str(error), f"fixture:{name}: wrong assertion: {error}"
    else:
        raise AssertionError(f"fixture:{name}: negative fixture unexpectedly passed")


validate_report_html(valid_fixture, source="fixture:valid", generated=True)
validate_report_html(zero_fixture, source="fixture:zero", generated=True)
assert_fixture_rejected(
    "external-url",
    valid_fixture.replace('src="./shot.png"', 'src="//example.com/shot.png"'),
    "external resource",
)
assert_fixture_rejected(
    "non-relative-link",
    valid_fixture.replace('../superpowers/specs/bug-001.md', '/docs/specs/bug-001.md'),
    "link is not relative",
)
assert_fixture_rejected(
    "missing-anchor",
    valid_fixture.replace(' id="bug-001"', ""),
    "unstable bug anchor",
)
assert_fixture_rejected(
    "empty-alt",
    valid_fixture.replace('alt="저장 버튼 오류 화면"', 'alt=""'),
    "empty screenshot alt",
)
assert_fixture_rejected(
    "unresolved-token",
    valid_fixture.replace("</body>", "<p>__UNRESOLVED_TOKEN__</p></body>"),
    "unresolved token",
)
print("in-memory report fixtures passed: 2 positive, 5 negative")
print("bug-hunter configuration and report contract are valid")
PY
