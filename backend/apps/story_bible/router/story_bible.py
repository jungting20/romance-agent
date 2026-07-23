import logging
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response, status
from fastapi import Path as PathParameter
from fastapi.responses import JSONResponse

from apps.story_bible.composition import get_story_bible_service
from apps.story_bible.schemas.story_bible import (
    ApiErrorResponse,
    CharacterResponse,
    CreateCharacterRequest,
    FieldErrorResponse,
    SaveWorldEntriesRequest,
    StoryBibleResponse,
    StoryBibleSnapshotResponse,
    UpdateCharacterRequest,
    WorldEntryResponse,
)
from apps.story_bible.service.commands import (
    CreateCharacterCommand,
    SaveWorldEntriesCommand,
    UpdateCharacterCommand,
    WorldEntryAddition,
    WorldEntryUpdate,
)
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
from apps.story_bible.service.story_bible import StoryBibleService

router = APIRouter(tags=["Story Bible"])
logger = logging.getLogger(__name__)
ProjectIdPath = Annotated[str, PathParameter(alias="projectId", min_length=1)]
CharacterIdPath = Annotated[str, PathParameter(alias="characterId", min_length=1)]


@router.get(
    "/projects/{projectId}/story-bible",
    operation_id="getStoryBible",
    response_model=StoryBibleSnapshotResponse,
    responses={
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def get_story_bible(
    project_id: ProjectIdPath,
    service: Annotated[StoryBibleService, Depends(get_story_bible_service)],
) -> StoryBibleSnapshotResponse | JSONResponse:
    try:
        return _snapshot_response(service.get_story_bible(project_id))
    except ProjectNotFoundError:
        return _error_response(404, "STORY_BIBLE_NOT_FOUND", "세계관 정보를 찾을 수 없습니다.")
    except StoryBibleNotFoundError:
        return _error_response(404, "STORY_BIBLE_NOT_FOUND", "세계관 정보를 찾을 수 없습니다.")
    except StoryBiblePersistenceError:
        return _error_response(500, "INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")
    except Exception:
        logger.exception("Unexpected failure while reading Story Bible")
        return _error_response(500, "INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")


@router.post(
    "/projects/{projectId}/story-bible/characters",
    operation_id="createStoryBibleCharacter",
    status_code=status.HTTP_201_CREATED,
    response_model=StoryBibleSnapshotResponse,
    responses={
        400: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def create_character(
    project_id: ProjectIdPath,
    request: CreateCharacterRequest,
    response: Response,
    service: Annotated[StoryBibleService, Depends(get_story_bible_service)],
) -> StoryBibleSnapshotResponse | JSONResponse:
    command = CreateCharacterCommand(
        name=request.name,
        gender=request.gender,
        age=request.age,
        role=request.role,
        personality=request.personality,
        prose_style=request.prose_style,
        dialogue_style=request.dialogue_style,
        desire=request.desire,
        hidden_feeling=request.hidden_feeling,
    )
    try:
        snapshot = service.create_character(project_id, command)
        character_id = snapshot.story_bible.characters[-1].id
        response.headers["Location"] = (
            f"/api/projects/{quote(project_id, safe='')}/story-bible/characters/"
            f"{quote(character_id, safe='')}"
        )
        return _snapshot_response(snapshot)
    except ProjectNotFoundError:
        return _error_response(404, "PROJECT_NOT_FOUND", "프로젝트를 찾을 수 없습니다.")
    except StoryBibleNotFoundError:
        return _error_response(404, "STORY_BIBLE_NOT_FOUND", "세계관 정보를 찾을 수 없습니다.")
    except InvalidCharacterError as error:
        return _invalid_character_response(error)
    except StoryBiblePersistenceError:
        return _error_response(500, "INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")
    except Exception:
        logger.exception("Unexpected failure while creating Story Bible character")
        return _error_response(500, "INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")


@router.patch(
    "/projects/{projectId}/story-bible/characters/{characterId}",
    operation_id="updateStoryBibleCharacter",
    response_model=StoryBibleSnapshotResponse,
    responses={
        400: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def update_character(
    project_id: ProjectIdPath,
    character_id: CharacterIdPath,
    request: UpdateCharacterRequest,
    service: Annotated[StoryBibleService, Depends(get_story_bible_service)],
) -> StoryBibleSnapshotResponse | JSONResponse:
    supplied = request.model_fields_set
    command = UpdateCharacterCommand(
        name=request.name if "name" in supplied else None,
        gender=request.gender if "gender" in supplied else None,
        age=request.age if "age" in supplied else None,
        role=request.role if "role" in supplied else None,
        personality=request.personality if "personality" in supplied else None,
        prose_style=request.prose_style if "prose_style" in supplied else None,
        dialogue_style=(request.dialogue_style if "dialogue_style" in supplied else None),
        desire=request.desire if "desire" in supplied else None,
        hidden_feeling=(request.hidden_feeling if "hidden_feeling" in supplied else None),
    )
    try:
        return _snapshot_response(service.update_character(project_id, character_id, command))
    except ProjectNotFoundError:
        return _error_response(404, "PROJECT_NOT_FOUND", "프로젝트를 찾을 수 없습니다.")
    except StoryBibleNotFoundError:
        return _error_response(404, "STORY_BIBLE_NOT_FOUND", "세계관 정보를 찾을 수 없습니다.")
    except CharacterNotFoundError:
        return _error_response(404, "CHARACTER_NOT_FOUND", "인물을 찾을 수 없습니다.")
    except InvalidCharacterError as error:
        return _invalid_character_response(error)
    except StoryBiblePersistenceError:
        return _error_response(500, "INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")
    except Exception:
        logger.exception("Unexpected failure while updating Story Bible character")
        return _error_response(500, "INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")


@router.put(
    "/projects/{projectId}/story-bible/world-entries",
    operation_id="saveWorldEntries",
    response_model=StoryBibleSnapshotResponse,
    responses={
        400: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def save_world_entries(
    project_id: ProjectIdPath,
    request: SaveWorldEntriesRequest,
    service: Annotated[StoryBibleService, Depends(get_story_bible_service)],
) -> StoryBibleSnapshotResponse | JSONResponse:
    command = SaveWorldEntriesCommand(
        expected_revision=request.expected_revision,
        updates=tuple(
            WorldEntryUpdate(item.id, item.kind, item.title, item.description)
            for item in request.updates
        ),
        additions=tuple(
            WorldEntryAddition(item.kind, item.title, item.description)
            for item in request.additions
        ),
    )
    try:
        return _snapshot_response(service.save_world_entries(project_id, command))
    except ProjectNotFoundError:
        return _error_response(404, "STORY_BIBLE_NOT_FOUND", "세계관 정보를 찾을 수 없습니다.")
    except StoryBibleNotFoundError:
        return _error_response(404, "STORY_BIBLE_NOT_FOUND", "세계관 정보를 찾을 수 없습니다.")
    except StoryBibleRevisionConflictError:
        return _error_response(
            409,
            "STORY_BIBLE_REVISION_CONFLICT",
            "다른 위치에서 세계관이 먼저 수정되었습니다.",
        )
    except InvalidWorldEntriesError as error:
        return _error_response(
            422,
            "INVALID_WORLD_ENTRIES",
            error.message,
            tuple(
                FieldErrorResponse(path=item.path, message=item.message)
                for item in error.field_errors
            ),
        )
    except StoryBiblePersistenceError:
        return _error_response(500, "INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")
    except Exception:
        logger.exception("Unexpected failure while saving Story Bible world entries")
        return _error_response(500, "INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")


def _snapshot_response(snapshot: StoryBibleSnapshot) -> StoryBibleSnapshotResponse:
    return StoryBibleSnapshotResponse(
        storyBible=StoryBibleResponse(
            projectId=snapshot.story_bible.project_id,
            characters=tuple(
                CharacterResponse(
                    id=character.id,
                    name=character.name,
                    gender=character.gender,
                    age=character.age,
                    role=character.role,
                    personality=character.personality,
                    proseStyle=character.prose_style,
                    dialogueStyle=character.dialogue_style,
                    desire=character.desire,
                    hiddenFeeling=character.hidden_feeling,
                )
                for character in snapshot.story_bible.characters
            ),
            worldEntries=tuple(
                WorldEntryResponse(
                    id=entry.id,
                    kind=entry.kind,
                    title=entry.title,
                    description=entry.description,
                )
                for entry in snapshot.story_bible.world_entries
            ),
        ),
        storyBibleRevision=snapshot.revision,
    )


def _error_response(
    status_code: int,
    code: str,
    message: str,
    field_errors: tuple[FieldErrorResponse, ...] = (),
) -> JSONResponse:
    error = ApiErrorResponse(
        code=code,
        message=message,
        fieldErrors=field_errors,
    )
    return JSONResponse(status_code=status_code, content=error.model_dump(by_alias=True))


def _invalid_character_response(error: InvalidCharacterError) -> JSONResponse:
    return _error_response(
        422,
        "INVALID_CHARACTER",
        error.message,
        tuple(
            FieldErrorResponse(path=item.path, message=item.message) for item in error.field_errors
        ),
    )
