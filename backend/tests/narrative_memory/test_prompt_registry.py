import json
from hashlib import sha256

import pytest

from apps.narrative_memory.service.chunking import SceneChunk
from apps.narrative_memory.service.scene_analysis_types import AnalyzeSceneRequest, KnownIdentity
from infrastructure.llm.prompt_registry import (
    FilePromptRegistry,
    PromptDefinitionError,
    render_scene_analysis_user_prompt,
)


def _write_prompt(tmp_path, raw_bytes: bytes) -> None:
    prompt_directory = tmp_path / "scene-analysis"
    prompt_directory.mkdir(exist_ok=True)
    (prompt_directory / "system.md").write_bytes(raw_bytes)


def _valid_prompt(*, version: str = "1", schema: str = "chunk-analysis-extraction-v1") -> bytes:
    return (
        "---\n"
        "prompt_id: scene-analysis\n"
        f"version: {version}\n"
        f"result_schema: {schema}\n"
        "---\n"
        "Extract only asserted facts.\n"
    ).encode()


def test_file_prompt_registry_loads_exact_versioned_prompt(tmp_path) -> None:
    raw_bytes = _valid_prompt()
    _write_prompt(tmp_path, raw_bytes)

    prompt = FilePromptRegistry(tmp_path).load("scene-analysis")

    assert prompt.prompt_id == "scene-analysis"
    assert prompt.version == 1
    assert prompt.result_schema == "chunk-analysis-extraction-v1"
    assert prompt.body == "Extract only asserted facts.\n"
    assert prompt.content_hash == f"sha256:{sha256(raw_bytes).hexdigest()}"
    assert prompt.raw_bytes == raw_bytes


def test_file_prompt_registry_reloads_changed_file_without_restart(tmp_path) -> None:
    first_bytes = _valid_prompt()
    _write_prompt(tmp_path, first_bytes)
    registry = FilePromptRegistry(tmp_path)

    first = registry.load("scene-analysis")
    changed_bytes = _valid_prompt(version="2").replace(b"asserted facts", b"explicit facts")
    _write_prompt(tmp_path, changed_bytes)
    second = registry.load("scene-analysis")

    assert first.version == 1
    assert second.version == 2
    assert second.body == "Extract only explicit facts.\n"
    assert second.raw_bytes == changed_bytes
    assert second.content_hash != first.content_hash


def test_file_prompt_registry_rejects_invalid_utf8(tmp_path) -> None:
    _write_prompt(tmp_path, _valid_prompt() + b"\xff")

    with pytest.raises(PromptDefinitionError, match="UTF-8"):
        FilePromptRegistry(tmp_path).load("scene-analysis")


@pytest.mark.parametrize(
    ("raw_bytes", "message"),
    [
        (b"prompt_id: scene-analysis\n", "front matter"),
        (
            b"---\nprompt_id: scene-analysis\nversion: 1\nresult_schema: "
            b"chunk-analysis-extraction-v1\n",
            "front matter",
        ),
        (
            b"---\nprompt_id: scene-analysis\nversion: 1\n---\nbody\n",
            "metadata keys",
        ),
        (
            b"---\nprompt_id: scene-analysis\nversion: 1\nresult_schema: "
            b"chunk-analysis-extraction-v1\nowner: team\n---\nbody\n",
            "metadata key",
        ),
        (
            b"---\nprompt_id: scene-analysis\nprompt_id: scene-analysis\nversion: 1\n"
            b"result_schema: chunk-analysis-extraction-v1\n---\nbody\n",
            "duplicate metadata",
        ),
    ],
)
def test_file_prompt_registry_rejects_malformed_front_matter(
    tmp_path, raw_bytes: bytes, message: str
) -> None:
    _write_prompt(tmp_path, raw_bytes)

    with pytest.raises(PromptDefinitionError, match=message):
        FilePromptRegistry(tmp_path).load("scene-analysis")


@pytest.mark.parametrize("version", ["0", "-1", "one", "1.5"])
def test_file_prompt_registry_rejects_non_positive_integer_version(tmp_path, version: str) -> None:
    _write_prompt(tmp_path, _valid_prompt(version=version))

    with pytest.raises(PromptDefinitionError, match="positive integer"):
        FilePromptRegistry(tmp_path).load("scene-analysis")


@pytest.mark.parametrize(
    "prompt_id",
    [
        "",
        "/scene-analysis",
        "../scene-analysis",
        "scene-analysis/",
        r"..\outside",
        r"C:\outside",
        "C:/outside",
        r"\\server\share\prompt",
    ],
)
def test_file_prompt_registry_rejects_invalid_prompt_id(tmp_path, prompt_id: str) -> None:
    with pytest.raises(PromptDefinitionError, match="invalid prompt ID"):
        FilePromptRegistry(tmp_path).load(prompt_id)


def test_file_prompt_registry_rejects_prompt_symlink_outside_root(tmp_path) -> None:
    prompt_root = tmp_path / "prompts"
    prompt_root.mkdir()
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    (outside_directory / "system.md").write_bytes(_valid_prompt())
    try:
        (prompt_root / "scene-analysis").symlink_to(outside_directory, target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"platform cannot create directory symlinks: {error}")

    with pytest.raises(PromptDefinitionError, match="outside configured root"):
        FilePromptRegistry(prompt_root).load("scene-analysis")


def test_file_prompt_registry_preserves_valid_nested_prompt_ids(tmp_path) -> None:
    prompt_id = "narrative/scene-analysis"
    prompt_directory = tmp_path / "narrative" / "scene-analysis"
    prompt_directory.mkdir(parents=True)
    raw_bytes = _valid_prompt().replace(b"scene-analysis", prompt_id.encode(), 1)
    (prompt_directory / "system.md").write_bytes(raw_bytes)

    prompt = FilePromptRegistry(tmp_path).load(prompt_id)

    assert prompt.prompt_id == prompt_id
    assert prompt.raw_bytes == raw_bytes


def test_file_prompt_registry_translates_missing_prompt_file_error(tmp_path) -> None:
    with pytest.raises(PromptDefinitionError, match="resolve prompt path"):
        FilePromptRegistry(tmp_path).load("scene-analysis")


def test_file_prompt_registry_rejects_metadata_prompt_id_mismatch(tmp_path) -> None:
    _write_prompt(tmp_path, _valid_prompt().replace(b"scene-analysis", b"other-prompt", 1))

    with pytest.raises(PromptDefinitionError, match="prompt ID"):
        FilePromptRegistry(tmp_path).load("scene-analysis")


def test_file_prompt_registry_rejects_unsupported_result_schema(tmp_path) -> None:
    _write_prompt(tmp_path, _valid_prompt(schema="chunk-analysis-extraction-v2"))

    with pytest.raises(PromptDefinitionError, match="unsupported result schema"):
        FilePromptRegistry(tmp_path).load("scene-analysis")


def test_render_scene_analysis_user_prompt_uses_stable_typed_json(monkeypatch) -> None:
    monkeypatch.setenv("NARRATIVE_LLM_MODEL", "secret-provider:model")
    monkeypatch.setenv("SECRET_API_KEY", "do-not-render")
    request = AnalyzeSceneRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=7,
        scene_sequence=3,
        text="whole scene must not be rendered",
        known_entities=(
            KnownIdentity("entity:z", "zoe", "Zoe", ("Z",)),
            KnownIdentity("entity:a", "alex", "Alex"),
        ),
        known_places=(
            KnownIdentity("place:z", "zoo", "Zoo"),
            KnownIdentity("place:a", "atrium", "Atrium", ("Hall",)),
        ),
    )
    chunk = SceneChunk(
        chunk_id="scene-01:r7:0001",
        scene_id="scene-01",
        manuscript_revision=7,
        ordinal=1,
        start_offset=250,
        end_offset=276,
        content_hash="sha256:chunk",
        text="Alex met Zoe at the atrium.",
    )

    rendered = render_scene_analysis_user_prompt(request, chunk)

    assert json.loads(rendered) == {
        "chunk": {
            "chunk_id": "scene-01:r7:0001",
            "content_hash": "sha256:chunk",
            "end_offset": 276,
            "ordinal": 1,
            "start_offset": 250,
            "text": "Alex met Zoe at the atrium.",
        },
        "known_entities": [
            {
                "aliases": [],
                "display_name": "Alex",
                "identity_key": "entity:a",
                "normalized_name": "alex",
            },
            {
                "aliases": ["Z"],
                "display_name": "Zoe",
                "identity_key": "entity:z",
                "normalized_name": "zoe",
            },
        ],
        "known_places": [
            {
                "aliases": ["Hall"],
                "display_name": "Atrium",
                "identity_key": "place:a",
                "normalized_name": "atrium",
            },
            {
                "aliases": [],
                "display_name": "Zoo",
                "identity_key": "place:z",
                "normalized_name": "zoo",
            },
        ],
        "project_id": "project-01",
        "scene_id": "scene-01",
        "scene_revision": 7,
        "scene_sequence": 3,
    }
    assert render_scene_analysis_user_prompt(request, chunk) == rendered
    assert "whole scene must not be rendered" not in rendered
    assert "secret-provider:model" not in rendered
    assert "do-not-render" not in rendered
