import asyncio
import traceback
from dataclasses import FrozenInstanceError

import pytest
from narrative_analysis_agent import (
    NarrativeAnalysisError,
    ProjectKnowledgeGraphSnapshot,
    SceneAnalysis,
    SceneAnalysisRequest,
)
from narrative_analysis_agent.models import Document, Entities, KnowledgeGraphOutput

from apps.narrative_memory.repository.snapshot_repository import (
    SnapshotCorruptionError,
    SnapshotVersionConflict,
    StoredProjectSnapshot,
)
from apps.narrative_memory.service.models import SceneGraphRecord
from apps.narrative_memory.service.scene_analysis_use_case import (
    AnalyzeSceneInput,
    AnalyzeSceneUseCase,
    SceneAnalysisApplicationError,
)


class RecordingAgent:
    def __init__(self, result: SceneAnalysis) -> None:
        self.result = result
        self.requests: list[SceneAnalysisRequest] = []

    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis:
        self.requests.append(request)
        return self.result


class FailingAgent:
    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis:
        del request
        try:
            raise RuntimeError("SECRET_PROVIDER_CAUSE")
        except RuntimeError as error:
            raise NarrativeAnalysisError("SECRET_PROVIDER_MESSAGE") from error


class CancelledAgent:
    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysis:
        del request
        raise asyncio.CancelledError


class RecordingSnapshotRepository:
    def __init__(
        self,
        *,
        current: StoredProjectSnapshot | None,
        scenes: tuple[SceneGraphRecord, ...],
        current_error: Exception | None = None,
        commit_error: Exception | None = None,
    ) -> None:
        self.current = current
        self.scenes = scenes
        self.current_error = current_error
        self.commit_error = commit_error
        self.current_requests: list[str] = []
        self.scene_requests: list[str] = []
        self.commit_attempts = 0
        self.commits: list[tuple[int | None, SceneGraphRecord, ProjectKnowledgeGraphSnapshot]] = []

    def initialize(self) -> None:
        pass

    def get_current(self, project_id: str) -> StoredProjectSnapshot | None:
        self.current_requests.append(project_id)
        if self.current_error is not None:
            raise self.current_error
        return self.current

    def get_scene_graphs(self, project_id: str) -> tuple[SceneGraphRecord, ...]:
        self.scene_requests.append(project_id)
        return self.scenes

    def commit_scene(
        self,
        expected_version: int | None,
        scene: SceneGraphRecord,
        snapshot: ProjectKnowledgeGraphSnapshot,
    ) -> StoredProjectSnapshot:
        self.commit_attempts += 1
        if self.commit_error is not None:
            raise self.commit_error
        self.commits.append((expected_version, scene, snapshot))
        return _stored(snapshot)


def test_use_case_converts_immutable_input_to_the_exact_public_request() -> None:
    analysis = _analysis()
    agent = RecordingAgent(analysis)
    repository = RecordingSnapshotRepository(current=None, scenes=())
    input_value = _input()

    result = asyncio.run(AnalyzeSceneUseCase(agent, repository).execute(input_value))

    assert result is analysis
    assert agent.requests == [
        SceneAnalysisRequest(
            project_id="project-01",
            scene_id="scene-01",
            scene_revision=3,
            scene_sequence=7,
            text="서윤이 온실에 도착했다.",
        )
    ]
    with pytest.raises(FrozenInstanceError):
        input_value.text = "changed"  # type: ignore[misc]


def test_use_case_persists_scene_and_project_after_successful_analysis() -> None:
    analysis = _analysis(source_snapshot_version=0)
    repository = RecordingSnapshotRepository(current=None, scenes=())

    result = asyncio.run(
        AnalyzeSceneUseCase(RecordingAgent(analysis), repository).execute(_input())
    )

    assert result is analysis
    assert len(repository.commits) == 1
    expected_version, scene, project = repository.commits[0]
    assert expected_version is None
    assert scene.scene_id == "scene-01"
    assert scene.scene_revision == 3
    assert project.project_id == "project-01"
    assert project.snapshot_version == 0
    assert tuple(document.chapter_id for document in project.documents) == ("scene-01",)


def test_use_case_replaces_same_scene_and_builds_the_next_project_version() -> None:
    previous = _scene("scene-01", revision=2, sequence=1, summary="이전 요약")
    other = _scene("scene-02", revision=1, sequence=2, summary="다른 장면")
    current = _stored(_snapshot(version=4, scenes=(previous, other)))
    analysis = _analysis(source_snapshot_version=4, scene_sequence=1)
    repository = RecordingSnapshotRepository(
        current=current,
        scenes=(previous, other),
    )

    asyncio.run(
        AnalyzeSceneUseCase(RecordingAgent(analysis), repository).execute(_input(scene_sequence=1))
    )

    expected_version, scene, project = repository.commits[0]
    assert expected_version == 4
    assert scene.scene_id == previous.scene_id
    assert scene.scene_revision == 3
    assert project.snapshot_version == 5
    assert tuple(document.chapter_id for document in project.documents) == (
        "scene-01",
        "scene-02",
    )
    assert tuple(document.summary for document in project.documents) == ("", "다른 장면")


@pytest.mark.parametrize("source_snapshot_version", [3, 5])
def test_use_case_rejects_any_source_snapshot_version_mismatch_without_commit(
    source_snapshot_version: int,
) -> None:
    current = _stored(_snapshot(version=4, scenes=()))
    repository = RecordingSnapshotRepository(current=current, scenes=())

    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(
            AnalyzeSceneUseCase(
                RecordingAgent(_analysis(source_snapshot_version=source_snapshot_version)),
                repository,
            ).execute(_input())
        )

    _assert_sanitized(captured.value, "analysis used a stale project graph")
    assert repository.scene_requests == []
    assert repository.commit_attempts == 0
    assert repository.commits == []


def test_use_case_sanitizes_merge_failure_without_commit() -> None:
    repository = RecordingSnapshotRepository(current=None, scenes=())

    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(
            AnalyzeSceneUseCase(
                RecordingAgent(_analysis(project_id="SECRET_OTHER_PROJECT")),
                repository,
            ).execute(_input())
        )

    _assert_sanitized(captured.value, "SECRET_OTHER_PROJECT")
    assert repository.commit_attempts == 0
    assert repository.commits == []


def test_use_case_sanitizes_atomic_commit_failure_without_published_commit() -> None:
    repository = RecordingSnapshotRepository(
        current=None,
        scenes=(),
        commit_error=SnapshotVersionConflict("SECRET_COMMIT_CONFLICT"),
    )

    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(AnalyzeSceneUseCase(RecordingAgent(_analysis()), repository).execute(_input()))

    _assert_sanitized(captured.value, "SECRET_COMMIT_CONFLICT")
    assert repository.commit_attempts == 1
    assert repository.commits == []


def test_use_case_sanitizes_repository_read_failure() -> None:
    repository = RecordingSnapshotRepository(
        current=None,
        scenes=(),
        current_error=SnapshotCorruptionError("SECRET_CORRUPT_SNAPSHOT"),
    )

    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(AnalyzeSceneUseCase(RecordingAgent(_analysis()), repository).execute(_input()))

    _assert_sanitized(captured.value, "SECRET_CORRUPT_SNAPSHOT")
    assert repository.commit_attempts == 0


def test_use_case_sanitizes_public_agent_errors_before_repository_access() -> None:
    repository = RecordingSnapshotRepository(current=None, scenes=())

    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(AnalyzeSceneUseCase(FailingAgent(), repository).execute(_input()))

    _assert_sanitized(
        captured.value,
        "SECRET_PROVIDER_MESSAGE",
        "SECRET_PROVIDER_CAUSE",
    )
    assert repository.current_requests == []
    assert repository.commit_attempts == 0


def test_use_case_propagates_cancellation_before_repository_access() -> None:
    repository = RecordingSnapshotRepository(current=None, scenes=())

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(AnalyzeSceneUseCase(CancelledAgent(), repository).execute(_input()))

    assert repository.current_requests == []
    assert repository.commit_attempts == 0


def _input(*, scene_sequence: int = 7) -> AnalyzeSceneInput:
    return AnalyzeSceneInput(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=3,
        scene_sequence=scene_sequence,
        text="서윤이 온실에 도착했다.",
    )


def _analysis(
    *,
    source_snapshot_version: int = 0,
    project_id: str = "project-01",
    scene_sequence: int = 7,
) -> SceneAnalysis:
    return SceneAnalysis(
        project_id=project_id,
        scene_id="scene-01",
        scene_revision=3,
        scene_sequence=scene_sequence,
        source_snapshot_version=source_snapshot_version,
        chunks=(),
    )


def _scene(
    scene_id: str,
    *,
    revision: int,
    sequence: int,
    summary: str,
) -> SceneGraphRecord:
    return SceneGraphRecord(
        project_id="project-01",
        scene_id=scene_id,
        scene_revision=revision,
        scene_sequence=sequence,
        graph=KnowledgeGraphOutput(
            document=Document(
                chapter_id=scene_id,
                summary=summary,
                narrative_time="present",
            ),
            entities=Entities(),
        ),
    )


def _snapshot(
    *,
    version: int,
    scenes: tuple[SceneGraphRecord, ...],
) -> ProjectKnowledgeGraphSnapshot:
    return ProjectKnowledgeGraphSnapshot(
        project_id="project-01",
        snapshot_version=version,
        schema_version="project-knowledge-graph-snapshot-v2",
        documents=tuple(scene.graph.document for scene in scenes),
    )


def _stored(snapshot: ProjectKnowledgeGraphSnapshot) -> StoredProjectSnapshot:
    return StoredProjectSnapshot(snapshot=snapshot, payload=b"", content_hash="")


def _assert_sanitized(error: Exception, *secrets: str) -> None:
    assert error.args == ("scene analysis failed",)
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
    formatted = "".join(traceback.format_exception(error))
    for secret in secrets:
        assert secret not in formatted
