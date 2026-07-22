import asyncio
import inspect
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from narrative_analysis_agent import (
    AnalysisConfigurationError,
    KnownIdentity,
    LocationEventType,
    NarrativeAnalysisAgent,
    NarrativeAnalysisConfig,
    SceneAnalysisRequest,
)
from narrative_analysis_agent.assembly.models import (
    ExtractedLocationEvent,
    ExtractedRelationshipEvent,
    RelativeEvidence,
    SceneChunkExtraction,
)
from narrative_analysis_agent.extraction.agent import ScriptedChunkAnalyzer

ROOT = Path(__file__).parents[3]
PROMPT_ROOT = ROOT / "llm-agent/src/narrative_analysis_agent/prompts"


def _known_identities() -> tuple[tuple[KnownIdentity, ...], tuple[KnownIdentity, ...]]:
    return (
        (
            KnownIdentity("character:han-seoyun", "한서윤", "한서윤"),
            KnownIdentity("character:cha-mina", "차민아", "차민아"),
            KnownIdentity("character:kang-dohyeon", "강도현", "강도현"),
            KnownIdentity("character:yun-taegyeong", "윤태경", "윤태경"),
        ),
        (KnownIdentity("place:haedam-bookstore", "해담서점", "해담서점"),),
    )


def _relative_evidence(values: list[dict[str, object]]) -> tuple[RelativeEvidence, ...]:
    translated = []
    for value in values:
        chunk_id = str(value["chunk_id"])
        ordinal = int(chunk_id.rsplit(":", maxsplit=1)[1])
        chunk_start = ordinal * 250
        translated.append(
            RelativeEvidence(
                start_offset=int(value["start_offset"]) - chunk_start,
                end_offset=int(value["end_offset"]) - chunk_start,
                text=str(value["text"]),
            )
        )
    return tuple(translated)


def _acceptance_scripts(expected: dict[str, object]) -> dict[str, tuple[SceneChunkExtraction, ...]]:
    scene_id = str(expected["scene_id"])
    scene_revision = int(expected["scene_revision"])
    by_chunk: dict[str, dict[str, list[object]]] = {
        f"{scene_id}:r{scene_revision}:{ordinal:04d}": {
            "relationship_events": [],
            "location_events": [],
        }
        for ordinal in range(5)
    }
    for raw in expected["relationship_events"]:  # type: ignore[union-attr]
        event = dict(raw)
        evidence = event["evidence"]
        chunk_id = str(evidence[0]["chunk_id"])
        by_chunk[chunk_id]["relationship_events"].append(
            ExtractedRelationshipEvent(
                subject_ref=str(event["subject_key"]),
                object_ref=str(event["object_key"]),
                category=event["category"],  # type: ignore[arg-type]
                description=str(event["description"]),
                confidence=float(event["confidence"]),
                evidence=_relative_evidence(evidence),
            )
        )
    for raw in expected["location_events"]:  # type: ignore[union-attr]
        event = dict(raw)
        evidence = event["evidence"]
        chunk_id = str(evidence[0]["chunk_id"])
        by_chunk[chunk_id]["location_events"].append(
            ExtractedLocationEvent(
                character_ref=str(event["character_key"]),
                place_ref=str(event["place_key"]),
                event_type=LocationEventType(str(event["event_type"])),
                description=str(event["description"]),
                confidence=float(event["confidence"]),
                evidence=_relative_evidence(evidence),
            )
        )
    return {
        chunk_id: (
            SceneChunkExtraction(
                summary=str(expected["summary"]) if chunk_id.endswith("0000") else "",
                relationship_events=tuple(values["relationship_events"]),
                location_events=tuple(values["location_events"]),
            ),
        )
        for chunk_id, values in by_chunk.items()
    }


def test_public_facade_matches_repository_snapshot_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from narrative_analysis_agent import facade

    input_text = ROOT.joinpath("input.txt").read_text().rstrip("\n")
    expected = json.loads(ROOT.joinpath("relationships.json").read_text())
    assert len(input_text) == 1_194
    analyzer = ScriptedChunkAnalyzer(_acceptance_scripts(expected))
    monkeypatch.setattr(facade, "ScriptedChunkAnalyzer", lambda: analyzer)
    monkeypatch.setattr(facade, "uuid4", lambda: "run-acceptance")
    agent = NarrativeAnalysisAgent(
        NarrativeAnalysisConfig(
            model_name="mock",
            prompt_root=PROMPT_ROOT,
            audit_path=tmp_path / "agent-audit.sqlite3",
        )
    )
    known_entities, known_places = _known_identities()
    request = SceneAnalysisRequest(
        project_id="project-acceptance",
        scene_id="scene-reunion-at-haedam",
        scene_revision=1,
        scene_sequence=7,
        text=input_text,
        known_entities=known_entities,
        known_places=known_places,
    )

    result = asyncio.run(agent.analyze_scene(request))

    actual = json.loads(json.dumps(asdict(result.snapshot), ensure_ascii=False))
    assert actual == expected
    assert result.run_id == "run-acceptance"
    assert [call.chunk_id for call in analyzer.calls] == [
        f"scene-reunion-at-haedam:r1:{ordinal:04d}" for ordinal in range(5)
    ]
    assert (tmp_path / "agent-audit.sqlite3").is_file()


def test_blank_model_is_rejected_before_provider_or_audit_initialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from narrative_analysis_agent import facade

    def unexpected_initialization(*args: object, **kwargs: object) -> None:
        raise AssertionError("provider or audit must not initialize")

    monkeypatch.setattr(facade, "PydanticAIChunkAnalyzer", unexpected_initialization)
    monkeypatch.setattr(facade, "ScriptedChunkAnalyzer", unexpected_initialization)
    monkeypatch.setattr(facade, "SQLiteAgentAudit", unexpected_initialization)

    with pytest.raises(AnalysisConfigurationError, match="model") as captured:
        NarrativeAnalysisAgent(
            NarrativeAnalysisConfig("  ", PROMPT_ROOT, tmp_path / "audit.sqlite3")
        )

    assert captured.value.run_id is None


def test_facade_exposes_only_analyze_scene_as_a_public_method() -> None:
    public_methods = {
        name
        for name, member in inspect.getmembers(NarrativeAnalysisAgent, inspect.isfunction)
        if not name.startswith("_")
    }

    assert public_methods == {"analyze_scene"}
