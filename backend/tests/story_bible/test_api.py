from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from apps.story_bible.router import story_bible as router_module
from apps.story_bible.router.story_bible import get_story_bible_service
from apps.story_bible.service.story_bible import (
    Character,
    FieldError,
    InvalidWorldEntriesError,
    StoryBible,
    StoryBibleNotFoundError,
    StoryBiblePersistenceError,
    StoryBibleRevisionConflictError,
    StoryBibleSnapshot,
    WorldEntry,
)
from main import app


def snapshot() -> StoryBibleSnapshot:
    return StoryBibleSnapshot(
        story_bible=StoryBible(
            project_id="silver-garden",
            characters=(
                Character(
                    id="silver-garden-character-1",
                    name="서윤",
                    role="protagonist",
                    desire="선택을 지키고 싶다.",
                    hidden_feeling="진심을 확인하고 싶다.",
                ),
            ),
            world_entries=(
                WorldEntry(
                    id="silver-garden-world-1",
                    kind="place",
                    title="비가 그친 온실",
                    description="마지막 만남의 장소",
                ),
            ),
        ),
        revision=2,
    )


class StubService:
    def __init__(self, outcome: StoryBibleSnapshot | Exception) -> None:
        self.outcome = outcome
        self.calls: list[tuple[object, ...]] = []

    def get_story_bible(self, project_id: str) -> StoryBibleSnapshot:
        self.calls.append((project_id,))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    def save_world_entries(self, project_id: str, command: object) -> StoryBibleSnapshot:
        self.calls.append((project_id, command))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def override_service(service: StubService) -> None:
    app.dependency_overrides[get_story_bible_service] = lambda: service


def expected_snapshot() -> dict[str, object]:
    return {
        "storyBible": {
            "projectId": "silver-garden",
            "characters": [
                {
                    "id": "silver-garden-character-1",
                    "name": "서윤",
                    "role": "protagonist",
                    "desire": "선택을 지키고 싶다.",
                    "hiddenFeeling": "진심을 확인하고 싶다.",
                }
            ],
            "worldEntries": [
                {
                    "id": "silver-garden-world-1",
                    "kind": "place",
                    "title": "비가 그친 온실",
                    "description": "마지막 만남의 장소",
                }
            ],
        },
        "storyBibleRevision": 2,
    }


def error(code: str, message: str, field_errors: list[dict[str, str]] | None = None):
    return {"code": code, "message": message, "fieldErrors": field_errors or []}


def test_get_story_bible_returns_snapshot(client: TestClient) -> None:
    service = StubService(snapshot())
    override_service(service)

    response = client.get("/projects/silver-garden/story-bible")

    assert response.status_code == 200
    assert response.json() == expected_snapshot()
    assert service.calls == [("silver-garden",)]


@pytest.mark.parametrize(
    ("outcome", "status", "body"),
    [
        (
            StoryBibleNotFoundError(),
            404,
            error("STORY_BIBLE_NOT_FOUND", "세계관 정보를 찾을 수 없습니다."),
        ),
        (
            StoryBiblePersistenceError(),
            500,
            error("INTERNAL_ERROR", "잠시 후 다시 시도해 주세요."),
        ),
    ],
)
def test_get_story_bible_maps_documented_errors(
    client: TestClient, outcome: Exception, status: int, body: dict[str, object]
) -> None:
    override_service(StubService(outcome))

    response = client.get("/projects/silver-garden/story-bible")

    assert response.status_code == status
    assert response.json() == body


def test_get_story_bible_maps_unexpected_failure_to_internal_error(client: TestClient) -> None:
    override_service(StubService(RuntimeError("unexpected")))

    response = client.get("/projects/silver-garden/story-bible")

    assert response.status_code == 500
    assert response.json() == error("INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")


def valid_request() -> dict[str, object]:
    return {
        "expectedRevision": 1,
        "updates": [
            {
                "id": "silver-garden-world-1",
                "kind": "place",
                "title": "유리 온실",
                "description": "마지막 만남의 장소",
            }
        ],
        "additions": [],
    }


def test_save_world_entries_returns_authoritative_snapshot(client: TestClient) -> None:
    service = StubService(snapshot())
    override_service(service)

    response = client.put("/projects/silver-garden/story-bible/world-entries", json=valid_request())

    assert response.status_code == 200
    assert response.json() == expected_snapshot()
    project_id, command = service.calls[0]
    assert project_id == "silver-garden"
    assert command.expected_revision == 1  # type: ignore[attr-defined]
    assert command.updates[0].title == "유리 온실"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("payload", "raw_body"),
    [
        ({"updates": [], "additions": []}, None),
        ({**valid_request(), "unknown": True}, None),
        ({**valid_request(), "expectedRevision": "1"}, None),
        ({**valid_request(), "updates": "not-a-list"}, None),
        (
            {
                **valid_request(),
                "updates": [{**valid_request()["updates"][0], "kind": "invalid"}],  # type: ignore[index]
            },
            None,
        ),
        (None, "{bad json"),
    ],
)
def test_save_maps_all_request_schema_failures_to_malformed_request(
    client: TestClient, payload: dict[str, object] | None, raw_body: str | None
) -> None:
    override_service(StubService(snapshot()))
    if raw_body is None:
        response = client.put("/projects/silver-garden/story-bible/world-entries", json=payload)
    else:
        response = client.put(
            "/projects/silver-garden/story-bible/world-entries",
            content=raw_body,
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 400
    assert response.json() == error("MALFORMED_REQUEST", "요청 형식을 확인해 주세요.")


@pytest.mark.parametrize(
    ("outcome", "status", "body"),
    [
        (
            StoryBibleNotFoundError(),
            404,
            error("STORY_BIBLE_NOT_FOUND", "세계관 정보를 찾을 수 없습니다."),
        ),
        (
            StoryBibleRevisionConflictError(),
            409,
            error("STORY_BIBLE_REVISION_CONFLICT", "다른 위치에서 세계관이 먼저 수정되었습니다."),
        ),
        (
            InvalidWorldEntriesError(
                "세계관 항목을 확인해 주세요.",
                (FieldError("updates[0].title", "제목을 입력해 주세요."),),
            ),
            422,
            error(
                "INVALID_WORLD_ENTRIES",
                "세계관 항목을 확인해 주세요.",
                [{"path": "updates[0].title", "message": "제목을 입력해 주세요."}],
            ),
        ),
        (
            StoryBiblePersistenceError(),
            500,
            error("INTERNAL_ERROR", "잠시 후 다시 시도해 주세요."),
        ),
    ],
)
def test_save_world_entries_maps_documented_service_errors(
    client: TestClient, outcome: Exception, status: int, body: dict[str, object]
) -> None:
    override_service(StubService(outcome))

    response = client.put("/projects/silver-garden/story-bible/world-entries", json=valid_request())

    assert response.status_code == status
    assert response.json() == body


def test_save_world_entries_maps_unexpected_failure_to_internal_error(client: TestClient) -> None:
    override_service(StubService(RuntimeError("unexpected")))

    response = client.put("/projects/silver-garden/story-bible/world-entries", json=valid_request())

    assert response.status_code == 500
    assert response.json() == error("INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")


@pytest.mark.parametrize(
    ("method", "path", "request_kwargs"),
    [
        ("GET", "/projects/silver-garden/story-bible", {}),
        (
            "PUT",
            "/projects/silver-garden/story-bible/world-entries",
            {"json": valid_request()},
        ),
    ],
)
def test_dependency_construction_failure_maps_to_internal_error(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    request_kwargs: dict[str, object],
) -> None:
    monkeypatch.setenv("ROMANCE_AGENT_DATA_ROOT", "/configured/data")

    def fail_repository_construction(_data_root: object) -> None:
        raise OSError("resolve failed")

    monkeypatch.setattr(router_module, "FileStoryBibleRepository", fail_repository_construction)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.request(method, path, **request_kwargs)

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == error("INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")


def test_story_bible_operations_preserve_approved_operation_ids() -> None:
    paths = app.openapi()["paths"]

    assert paths["/projects/{projectId}/story-bible"]["get"]["operationId"] == "getStoryBible"
    assert (
        paths["/projects/{projectId}/story-bible/world-entries"]["put"]["operationId"]
        == "saveWorldEntries"
    )
