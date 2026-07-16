import logging
import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import Path as PathParameter
from fastapi.responses import JSONResponse

from apps.story_bible.repository.story_bible import FileStoryBibleRepository
from apps.story_bible.schemas.story_bible import (
    ApiErrorResponse,
    CharacterResponse,
    FieldErrorResponse,
    SaveWorldEntriesRequest,
    StoryBibleResponse,
    StoryBibleSnapshotResponse,
    WorldEntryResponse,
)
from apps.story_bible.service.story_bible import (
    InvalidWorldEntriesError,
    SaveWorldEntriesCommand,
    StoryBibleNotFoundError,
    StoryBiblePersistenceError,
    StoryBibleRevisionConflictError,
    StoryBibleService,
    StoryBibleSnapshot,
    WorldEntryAddition,
    WorldEntryUpdate,
)

router = APIRouter(tags=["Story Bible"])
logger = logging.getLogger(__name__)
ProjectIdPath = Annotated[str, PathParameter(alias="projectId", min_length=1)]


class StoryBibleDependencyError(Exception):
    """The Story Bible service could not be composed for a request."""


def get_story_bible_service() -> StoryBibleService:
    try:
        data_root = Path(os.environ["ROMANCE_AGENT_DATA_ROOT"])
        repository = FileStoryBibleRepository(data_root)
        return StoryBibleService(
            repository,
            lambda project_id: f"{project_id}-world-{uuid.uuid4().hex}",
        )
    except Exception as error:
        logger.exception("Could not compose Story Bible service")
        raise StoryBibleDependencyError from error


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
    except StoryBibleNotFoundError:
        return _error_response(404, "STORY_BIBLE_NOT_FOUND", "세계관 정보를 찾을 수 없습니다.")
    except StoryBiblePersistenceError:
        return _error_response(500, "INTERNAL_ERROR", "잠시 후 다시 시도해 주세요.")
    except Exception:
        logger.exception("Unexpected failure while reading Story Bible")
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
                    role=character.role,
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
