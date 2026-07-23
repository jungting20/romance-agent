from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from apps.story_bible import composition as composition_module
from apps.story_bible.composition import (
    StoryBibleDependencyError,
    get_story_bible_service,
)
from apps.story_bible.domain.models import Character, StoryBible, WorldEntry
from apps.story_bible.router import story_bible as router_module
from apps.story_bible.service.commands import FieldError
from apps.story_bible.service.errors import (
    CharacterNotFoundError,
    InvalidCharacterError,
    InvalidWorldEntriesError,
    ProjectNotFoundError,
    StoryBibleNotFoundError,
    StoryBiblePersistenceError,
    StoryBibleRevisionConflictError,
)
from apps.story_bible.service.models import StoryBibleSnapshot
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

    def create_character(self, project_id: str, command: object) -> StoryBibleSnapshot:
        self.calls.append((project_id, command))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    def update_character(
        self, project_id: str, character_id: str, command: object
    ) -> StoryBibleSnapshot:
        self.calls.append((project_id, character_id, command))
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
                    "gender": "",
                    "age": "",
                    "role": "protagonist",
                    "personality": "",
                    "proseStyle": "",
                    "dialogueStyle": "",
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


def valid_character_request() -> dict[str, str]:
    return {
        "name": "  민서  ",
        "gender": "여성",
        "age": "29세",
        "role": "서점 주인",
        "personality": "차분하다",
        "proseStyle": "짧은 문장",
        "dialogueStyle": "정중한 말투",
        "desire": "서점을 지키고 싶다",
        "hiddenFeeling": "두렵다",
    }


def test_create_character_returns_201_location_snapshot_and_typed_command(
    client: TestClient,
) -> None:
    service = StubService(snapshot())
    override_service(service)

    response = client.post(
        "/projects/silver-garden/story-bible/characters",
        json=valid_character_request(),
    )

    assert response.status_code == 201
    assert response.headers["location"] == (
        "/api/projects/silver-garden/story-bible/characters/silver-garden-character-1"
    )
    assert response.json() == expected_snapshot()
    project_id, command = service.calls[0]
    assert project_id == "silver-garden"
    assert command.age == "29세"  # type: ignore[attr-defined]
    assert command.prose_style == "짧은 문장"  # type: ignore[attr-defined]


def test_create_character_percent_encodes_location_path_segments(
    client: TestClient,
) -> None:
    result = snapshot()
    character = result.story_bible.characters[0]
    result = StoryBibleSnapshot(
        story_bible=StoryBible(
            project_id=result.story_bible.project_id,
            characters=(
                Character(
                    id="character/one ?#%",
                    name=character.name,
                    role=character.role,
                    desire=character.desire,
                    hidden_feeling=character.hidden_feeling,
                ),
            ),
            world_entries=result.story_bible.world_entries,
        ),
        revision=result.revision,
    )
    override_service(StubService(result))

    response = client.post(
        "/projects/silver%20garden%3F%23/story-bible/characters",
        json=valid_character_request(),
    )

    assert response.status_code == 201
    assert response.headers["location"] == (
        "/api/projects/silver%20garden%3F%23/story-bible/characters/character%2Fone%20%3F%23%25"
    )


def test_update_character_returns_snapshot_and_preserves_missing_fields_in_command(
    client: TestClient,
) -> None:
    service = StubService(snapshot())
    override_service(service)

    response = client.patch(
        "/projects/silver-garden/story-bible/characters/silver-garden-character-1",
        json={"age": "31세", "role": ""},
    )

    assert response.status_code == 200
    assert response.json() == expected_snapshot()
    project_id, character_id, command = service.calls[0]
    assert project_id == "silver-garden"
    assert character_id == "silver-garden-character-1"
    assert command.age == "31세"  # type: ignore[attr-defined]
    assert command.role == ""  # type: ignore[attr-defined]
    assert command.name is None  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "POST",
            "/projects/silver-garden/story-bible/characters",
            {**valid_character_request(), "age": 29},
        ),
        (
            "POST",
            "/projects/silver-garden/story-bible/characters",
            {**valid_character_request(), "unknown": "value"},
        ),
        (
            "PATCH",
            "/projects/silver-garden/story-bible/characters/character-1",
            {"age": 29},
        ),
        (
            "PATCH",
            "/projects/silver-garden/story-bible/characters/character-1",
            {"age": None},
        ),
        (
            "PATCH",
            "/projects/silver-garden/story-bible/characters/character-1",
            {"id": "replacement"},
        ),
    ],
)
def test_character_schema_failures_map_to_400_without_coercion(
    client: TestClient, method: str, path: str, payload: dict[str, object]
) -> None:
    override_service(StubService(snapshot()))

    response = client.request(method, path, json=payload)

    assert response.status_code == 400
    assert response.json() == error("MALFORMED_REQUEST", "요청 형식을 확인해 주세요.")


@pytest.mark.parametrize(
    ("method", "path", "payload", "service_error", "body"),
    [
        (
            "POST",
            "/projects/silver-garden/story-bible/characters",
            valid_character_request(),
            InvalidCharacterError(
                "인물 정보를 확인해 주세요.",
                (FieldError("name", "인물 이름을 입력해 주세요."),),
            ),
            error(
                "INVALID_CHARACTER",
                "인물 정보를 확인해 주세요.",
                [{"path": "name", "message": "인물 이름을 입력해 주세요."}],
            ),
        ),
        (
            "PATCH",
            "/projects/silver-garden/story-bible/characters/character-1",
            {},
            InvalidCharacterError("수정할 인물 정보가 필요합니다.", ()),
            error("INVALID_CHARACTER", "수정할 인물 정보가 필요합니다."),
        ),
    ],
)
def test_character_domain_validation_maps_to_exact_422(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object],
    service_error: Exception,
    body: dict[str, object],
) -> None:
    override_service(StubService(service_error))

    response = client.request(method, path, json=payload)

    assert response.status_code == 422
    assert response.json() == body


@pytest.mark.parametrize(
    ("service_error", "code", "message"),
    [
        (
            ProjectNotFoundError(),
            "PROJECT_NOT_FOUND",
            "프로젝트를 찾을 수 없습니다.",
        ),
        (
            StoryBibleNotFoundError(),
            "STORY_BIBLE_NOT_FOUND",
            "세계관 정보를 찾을 수 없습니다.",
        ),
    ],
)
def test_create_character_maps_all_not_found_errors(
    client: TestClient, service_error: Exception, code: str, message: str
) -> None:
    override_service(StubService(service_error))

    response = client.post(
        "/projects/silver-garden/story-bible/characters",
        json=valid_character_request(),
    )

    assert response.status_code == 404
    assert response.json() == error(code, message)


@pytest.mark.parametrize(
    ("service_error", "code", "message"),
    [
        (
            ProjectNotFoundError(),
            "PROJECT_NOT_FOUND",
            "프로젝트를 찾을 수 없습니다.",
        ),
        (
            StoryBibleNotFoundError(),
            "STORY_BIBLE_NOT_FOUND",
            "세계관 정보를 찾을 수 없습니다.",
        ),
        (CharacterNotFoundError(), "CHARACTER_NOT_FOUND", "인물을 찾을 수 없습니다."),
    ],
)
def test_update_character_maps_not_found_errors(
    client: TestClient, service_error: Exception, code: str, message: str
) -> None:
    override_service(StubService(service_error))

    response = client.patch(
        "/projects/silver-garden/story-bible/characters/character-1",
        json={"role": "조언자"},
    )

    assert response.status_code == 404
    assert response.json() == error(code, message)


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
            "POST",
            "/projects/silver-garden/story-bible/characters",
            {"json": valid_character_request()},
        ),
        (
            "PATCH",
            "/projects/silver-garden/story-bible/characters/character-1",
            {"json": {"role": "조언자"}},
        ),
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

    monkeypatch.setattr(
        composition_module,
        "FileStoryBibleRepository",
        fail_repository_construction,
    )

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.request(method, path, **request_kwargs)

    assert StoryBibleDependencyError in app.exception_handlers
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == error("INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")


def test_router_does_not_own_runtime_repository_composition() -> None:
    assert not hasattr(router_module, "FileStoryBibleRepository")


def test_story_bible_operations_preserve_approved_operation_ids() -> None:
    paths = app.openapi()["paths"]

    assert paths["/projects/{projectId}/story-bible"]["get"]["operationId"] == "getStoryBible"
    assert (
        paths["/projects/{projectId}/story-bible/world-entries"]["put"]["operationId"]
        == "saveWorldEntries"
    )
    collection_path = paths["/projects/{projectId}/story-bible/characters"]
    assert collection_path["post"]["operationId"] == "createStoryBibleCharacter"
    assert "delete" not in collection_path
    assert "409" not in collection_path["post"]["responses"]
    character_path = paths["/projects/{projectId}/story-bible/characters/{characterId}"]
    assert character_path["patch"]["operationId"] == "updateStoryBibleCharacter"
    assert "delete" not in character_path
    assert "409" not in character_path["patch"]["responses"]
