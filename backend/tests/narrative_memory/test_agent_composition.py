import asyncio
from pathlib import Path

import narrative_analysis_agent
import pytest
from llm_agent_audit import NoopAgentAuditSink
from narrative_analysis_agent import (
    NarrativeAnalysisAgent,
    SceneAnalysisRequest,
    packaged_prompt_path,
)
from narrative_analysis_agent.models import Character
from pydantic import ValidationError

import apps.narrative_memory.composition as composition
from apps.narrative_memory.repository.sqlite_snapshot_repository import (
    SQLiteSnapshotRepository,
)


def test_backend_builds_only_the_public_agent_facade(tmp_path: Path) -> None:
    prompt_path = tmp_path / "system.md"
    prompt_path.write_text("지시", encoding="utf-8")
    project_graph_path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(project_graph_path)
    repository.initialize()

    agent = composition.build_narrative_analysis_agent(
        model_name="test",
        prompt_path=prompt_path,
        project_graph_path=project_graph_path,
    )

    assert isinstance(agent, NarrativeAnalysisAgent)
    assert agent.prompt_path == prompt_path
    result = asyncio.run(agent.analyze_scene(_empty_request()))
    assert result.source_snapshot_version == 0


def test_backend_passes_application_owned_audit_sink_to_public_agent(
    tmp_path: Path,
) -> None:
    project_graph_path = tmp_path / "narrative-memory.sqlite3"
    SQLiteSnapshotRepository(project_graph_path).initialize()
    sink = NoopAgentAuditSink()

    agent = composition.build_narrative_analysis_agent(
        model_name="test",
        prompt_path=tmp_path / "system.md",
        project_graph_path=project_graph_path,
        audit_sink=sink,
    )

    assert agent._runner._sink is sink


def test_use_case_composition_initializes_repository_before_agent_with_same_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_graph_path = tmp_path / "narrative-memory.sqlite3"
    prompt_path = tmp_path / "system.md"
    calls: list[tuple[str, Path]] = []
    repositories = []
    agent = object()
    sink = NoopAgentAuditSink()

    class RecordingRepository:
        def __init__(self, path: Path) -> None:
            self.path = path
            repositories.append(self)
            calls.append(("repository", path))

        def initialize(self) -> None:
            calls.append(("initialize", self.path))

    def recording_agent_builder(
        *,
        model_name: str,
        prompt_path: Path,
        project_graph_path: Path,
        audit_sink: NoopAgentAuditSink | None = None,
    ) -> object:
        assert model_name == "test"
        assert prompt_path == tmp_path / "system.md"
        assert audit_sink is sink
        calls.append(("agent", project_graph_path))
        return agent

    monkeypatch.setattr(composition, "SQLiteSnapshotRepository", RecordingRepository)
    monkeypatch.setattr(
        composition,
        "build_narrative_analysis_agent",
        recording_agent_builder,
    )

    use_case = composition.build_analyze_scene_use_case(
        model_name="test",
        prompt_path=prompt_path,
        project_graph_path=project_graph_path,
        audit_sink=sink,
    )

    assert calls == [
        ("repository", project_graph_path),
        ("initialize", project_graph_path),
        ("agent", project_graph_path),
    ]
    assert all(path is project_graph_path for _, path in calls)
    assert use_case._agent is agent
    assert use_case._repository is repositories[0]


def test_editable_agent_loads_its_packaged_prompt_through_public_apis(
    tmp_path: Path,
) -> None:
    installed_package_root = Path(narrative_analysis_agent.__file__).resolve().parent
    prompt_path = packaged_prompt_path()
    project_graph_path = tmp_path / "narrative-memory.sqlite3"
    repository = SQLiteSnapshotRepository(project_graph_path)
    repository.initialize()
    agent = composition.build_narrative_analysis_agent(
        model_name="test",
        prompt_path=prompt_path,
        project_graph_path=project_graph_path,
    )

    result = asyncio.run(agent.analyze_scene(_empty_request()))

    assert installed_package_root == _worktree_agent_package_root()
    assert prompt_path == installed_package_root / "prompts" / "scene-analysis" / "system.md"
    assert result.chunks == ()


def test_backend_uses_final_editable_public_character_contract() -> None:
    assert Path(narrative_analysis_agent.__file__).resolve().parent == (
        _worktree_agent_package_root()
    )

    with pytest.raises(ValidationError):
        Character(
            id="character_001",
            canonical_name="서윤",
            aliases=(),
            description="",
            gender="unknown",
            age=None,
            occupation=None,
            affiliation=None,
            status="unknown",
            first_mention="",
            confidence=0.8,
        )


def _empty_request() -> SceneAnalysisRequest:
    return SceneAnalysisRequest(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=1,
        scene_sequence=1,
        text="",
    )


def _worktree_agent_package_root() -> Path:
    return (
        Path(__file__).resolve().parents[3] / "llm-agent" / "src" / "narrative_analysis_agent"
    ).resolve()
