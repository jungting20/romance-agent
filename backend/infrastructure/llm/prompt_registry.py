import json
from hashlib import sha256
from pathlib import Path

from apps.narrative_memory.service.chunking import SceneChunk
from apps.narrative_memory.service.scene_analysis_ports import PromptDefinition
from apps.narrative_memory.service.scene_analysis_types import AnalyzeSceneRequest, KnownIdentity

SUPPORTED_RESULT_SCHEMAS = {"chunk-analysis-extraction-v1"}
_REQUIRED_METADATA_KEYS = {"prompt_id", "version", "result_schema"}


class PromptDefinitionError(ValueError):
    pass


class FilePromptRegistry:
    def __init__(self, root: Path) -> None:
        self._root = root

    def load(self, prompt_id: str) -> PromptDefinition:
        if not prompt_id or any(part in {"", ".", ".."} for part in prompt_id.split("/")):
            raise PromptDefinitionError("invalid prompt ID")
        path = self._root / prompt_id / "system.md"
        return _parse_prompt_definition(prompt_id, path.read_bytes())


def render_scene_analysis_user_prompt(
    request: AnalyzeSceneRequest,
    chunk: SceneChunk,
) -> str:
    envelope = {
        "project_id": request.project_id,
        "scene_id": request.scene_id,
        "scene_revision": request.scene_revision,
        "scene_sequence": request.scene_sequence,
        "chunk": {
            "chunk_id": chunk.chunk_id,
            "ordinal": chunk.ordinal,
            "start_offset": chunk.start_offset,
            "end_offset": chunk.end_offset,
            "content_hash": chunk.content_hash,
            "text": chunk.text,
        },
        "known_entities": _render_known_catalog(request.known_entities),
        "known_places": _render_known_catalog(request.known_places),
    }
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_prompt_definition(prompt_id: str, raw_bytes: bytes) -> PromptDefinition:
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PromptDefinitionError("prompt must be valid UTF-8") from error

    lines = text.splitlines(keepends=True)
    if not lines or _line_content(lines[0]) != "---":
        raise PromptDefinitionError("prompt must start with front matter delimiter")

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if _line_content(line) == "---"),
        None,
    )
    if closing_index is None:
        raise PromptDefinitionError("prompt front matter requires a closing delimiter")

    metadata: dict[str, str] = {}
    for line in lines[1:closing_index]:
        content = _line_content(line)
        if ":" not in content:
            raise PromptDefinitionError("invalid prompt metadata line")
        key, value = (part.strip() for part in content.split(":", maxsplit=1))
        if key in metadata:
            raise PromptDefinitionError(f"duplicate metadata key: {key}")
        if key not in _REQUIRED_METADATA_KEYS:
            raise PromptDefinitionError(f"unexpected metadata key: {key}")
        if not value:
            raise PromptDefinitionError(f"prompt metadata value is required: {key}")
        metadata[key] = value

    if set(metadata) != _REQUIRED_METADATA_KEYS:
        raise PromptDefinitionError("prompt must contain exactly the required metadata keys")
    if metadata["prompt_id"] != prompt_id:
        raise PromptDefinitionError("metadata prompt ID does not match requested prompt ID")

    version_text = metadata["version"]
    if not version_text.isascii() or not version_text.isdecimal() or int(version_text) <= 0:
        raise PromptDefinitionError("prompt version must be a positive integer")
    version = int(version_text)

    result_schema = metadata["result_schema"]
    if result_schema not in SUPPORTED_RESULT_SCHEMAS:
        raise PromptDefinitionError(f"unsupported result schema: {result_schema}")

    return PromptDefinition(
        prompt_id=prompt_id,
        version=version,
        result_schema=result_schema,
        content_hash=f"sha256:{sha256(raw_bytes).hexdigest()}",
        raw_bytes=raw_bytes,
        body="".join(lines[closing_index + 1 :]),
    )


def _line_content(line: str) -> str:
    return line.removesuffix("\n").removesuffix("\r")


def _render_known_catalog(identities: tuple[KnownIdentity, ...]) -> list[dict[str, object]]:
    return [
        {
            "identity_key": identity.identity_key,
            "normalized_name": identity.normalized_name,
            "display_name": identity.display_name,
            "aliases": list(identity.aliases),
        }
        for identity in sorted(identities, key=lambda item: item.identity_key)
    ]
