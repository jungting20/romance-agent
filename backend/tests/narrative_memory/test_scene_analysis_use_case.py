import asyncio
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from narrative_analysis_agent import (
    AnalyzedChunk,
    CharacterMemory,
    MemoryTarget,
    NarrativeAnalysisError,
    ProjectKnowledgeGraphSnapshot,
    SceneAnalysis,
    SceneAnalysisRequest,
)
from narrative_analysis_agent.models import Character, Document, Entities, KnowledgeGraphOutput

from apps.narrative_memory.repository.snapshot_repository import (
    SnapshotCorruptionError,
    SnapshotRepositoryError,
    SnapshotVersionConflict,
    StoredProjectSnapshot,
)
from apps.narrative_memory.repository.sqlite_snapshot_repository import (
    SQLiteSnapshotRepository,
)
from apps.narrative_memory.service.models import SceneGraphRecord
from apps.narrative_memory.service.scene_analysis_use_case import (
    AnalyzeSceneInput,
    AnalyzeSceneUseCase,
    SceneAnalysisApplicationError,
)
from apps.narrative_memory.service.validation import ProjectInvariantError


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
        scenes_error: Exception | None = None,
        commit_error: Exception | None = None,
        update_on_commit: bool = False,
    ) -> None:
        self.current = current
        self.scenes = scenes
        self.current_error = current_error
        self.scenes_error = scenes_error
        self.commit_error = commit_error
        self.update_on_commit = update_on_commit
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
        if self.scenes_error is not None:
            raise self.scenes_error
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
        if self.update_on_commit:
            self.current = _stored(snapshot)
            self.scenes = tuple(item for item in self.scenes if item.scene_id != scene.scene_id) + (
                scene,
            )
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
    assert project.snapshot_version == 1
    assert tuple(document.chapter_id for document in project.documents) == ("scene-01",)


def test_use_case_persists_explicit_memory_in_scene_and_project_snapshots(
    tmp_path: Path,
) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()
    analysis = _analysis_with_memory()

    result = asyncio.run(
        AnalyzeSceneUseCase(RecordingAgent(analysis), repository).execute(_input_with_memory())
    )

    assert result is analysis
    scenes = repository.get_scene_graphs("project-01")
    current = repository.get_current("project-01")
    assert len(scenes) == 1
    assert current is not None
    scene_memory = scenes[0].graph.character_memories[0]
    assert scene_memory == CharacterMemory(
        id="memory_001",
        character_id="character_001",
        target=MemoryTarget(
            kind="described_event",
            reference_id=None,
            description="온실에서 나눈 약속",
        ),
        content="서윤은 온실에서 나눈 약속을 기억한다.",
        state="remembered",
        time_expression="그날",
        scene_sequence=7,
        evidence="약속을 기억했다",
        confidence=0.95,
    )
    assert current.snapshot.character_memories == (scene_memory,)


def test_use_case_rejected_memory_merge_publishes_no_scene_or_project_state(
    tmp_path: Path,
) -> None:
    repository = SQLiteSnapshotRepository(tmp_path / "narrative-memory.sqlite3")
    repository.initialize()
    analysis = _analysis_with_memory(evidence="원문에 없는 기억 근거")

    with pytest.raises(SceneAnalysisApplicationError):
        asyncio.run(
            AnalyzeSceneUseCase(RecordingAgent(analysis), repository).execute(_input_with_memory())
        )

    assert repository.get_scene_graphs("project-01") == ()
    assert repository.get_current("project-01") is None


def test_use_case_sanitizes_corrupt_description_only_memory_without_commit() -> None:
    analysis = _analysis_with_memory()
    chunk = analysis.chunks[0]
    memory = chunk.extraction.character_memories[0]
    target = memory.target.model_copy(update={"reference_id": "event_999"})
    corrupted_extraction = chunk.extraction.model_copy(
        update={"character_memories": (memory.model_copy(update={"target": target}),)}
    )
    corrupted_chunk = chunk.model_copy(update={"extraction": corrupted_extraction})
    corrupted_analysis = analysis.model_copy(update={"chunks": (corrupted_chunk,)})
    repository = RecordingSnapshotRepository(current=None, scenes=())

    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(
            AnalyzeSceneUseCase(RecordingAgent(corrupted_analysis), repository).execute(
                _input_with_memory()
            )
        )

    _assert_sanitized(captured.value, "event_999")
    assert repository.scene_requests == []
    assert repository.commit_attempts == 0
    assert repository.commits == []


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


@pytest.mark.parametrize("stage", ["current", "scenes", "commit"])
def test_use_case_sanitizes_repository_operational_failures(stage: str) -> None:
    operational_error = SnapshotRepositoryError(f"SECRET_{stage.upper()}_OPERATION")
    repository = RecordingSnapshotRepository(
        current=None,
        scenes=(),
        current_error=operational_error if stage == "current" else None,
        scenes_error=operational_error if stage == "scenes" else None,
        commit_error=operational_error if stage == "commit" else None,
    )

    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(AnalyzeSceneUseCase(RecordingAgent(_analysis()), repository).execute(_input()))

    _assert_sanitized(captured.value, operational_error.args[0])


def test_use_case_sanitizes_project_validation_failure_without_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_validation(snapshot: ProjectKnowledgeGraphSnapshot) -> None:
        del snapshot
        raise ProjectInvariantError("SECRET_PROJECT_VALIDATION")

    monkeypatch.setattr(
        "apps.narrative_memory.service.merge.validate_project_snapshot",
        fail_validation,
    )
    repository = RecordingSnapshotRepository(current=None, scenes=())

    with pytest.raises(SceneAnalysisApplicationError) as captured:
        asyncio.run(AnalyzeSceneUseCase(RecordingAgent(_analysis()), repository).execute(_input()))

    _assert_sanitized(captured.value, "SECRET_PROJECT_VALIDATION")
    assert repository.commit_attempts == 0


def test_two_first_analyses_from_conceptual_version_zero_cannot_both_commit() -> None:
    repository = RecordingSnapshotRepository(
        current=None,
        scenes=(),
        update_on_commit=True,
    )
    use_case = AnalyzeSceneUseCase(
        RecordingAgent(_analysis(source_snapshot_version=0)),
        repository,
    )

    asyncio.run(use_case.execute(_input()))
    with pytest.raises(SceneAnalysisApplicationError):
        asyncio.run(use_case.execute(_input()))

    assert [snapshot.snapshot_version for _, _, snapshot in repository.commits] == [1]
    assert repository.current is not None
    assert repository.current.snapshot.snapshot_version == 1


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


def _input_with_memory() -> AnalyzeSceneInput:
    return AnalyzeSceneInput(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=3,
        scene_sequence=7,
        text="서윤은 그날 온실에서 나눈 약속을 기억했다.",
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


def _analysis_with_memory(*, evidence: str = "약속을 기억했다") -> SceneAnalysis:
    text = "서윤은 그날 온실에서 나눈 약속을 기억했다."
    return SceneAnalysis(
        project_id="project-01",
        scene_id="scene-01",
        scene_revision=3,
        scene_sequence=7,
        source_snapshot_version=0,
        chunks=(
            AnalyzedChunk(
                chunk_id="scene-01:r3:c0",
                ordinal=0,
                start_offset=0,
                end_offset=len(text),
                text=text,
                extraction=KnowledgeGraphOutput(
                    document=Document(
                        chapter_id="scene-01",
                        summary="서윤이 과거의 약속을 명시적으로 기억한다.",
                        narrative_time="present",
                    ),
                    entities=Entities(
                        characters=(
                            Character(
                                id="character_007",
                                canonical_name="서윤",
                                description="약속을 기억하는 인물",
                                gender="female",
                                age=None,
                                occupation=None,
                                affiliation=None,
                                status="alive",
                                first_mention="서윤",
                                confidence=0.95,
                            ),
                        )
                    ),
                    character_memories=(
                        CharacterMemory(
                            id="memory_009",
                            character_id="character_007",
                            target=MemoryTarget(
                                kind="described_event",
                                reference_id=None,
                                description="온실에서 나눈 약속",
                            ),
                            content="서윤은 온실에서 나눈 약속을 기억한다.",
                            state="remembered",
                            time_expression="그날",
                            scene_sequence=7,
                            evidence=evidence,
                            confidence=0.95,
                        ),
                    ),
                ),
            ),
        ),
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
