import logging
import os
import uuid
from pathlib import Path

from apps.story_bible.repository.story_bible import FileStoryBibleRepository
from apps.story_bible.service.story_bible import StoryBibleService

logger = logging.getLogger(__name__)


class StoryBibleDependencyError(Exception):
    """The Story Bible service could not be composed for a request."""


def _new_world_entry_id(project_id: str) -> str:
    return f"{project_id}-world-{uuid.uuid4().hex}"


def get_story_bible_service() -> StoryBibleService:
    try:
        repository = FileStoryBibleRepository(Path(os.environ["ROMANCE_AGENT_DATA_ROOT"]))
        return StoryBibleService(repository, _new_world_entry_id)
    except Exception as error:
        logger.exception("Could not compose Story Bible service")
        raise StoryBibleDependencyError from error
