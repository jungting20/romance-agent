from typing import Protocol

from apps.story_bible.domain.models import StoryBible
from apps.story_bible.service.models import StoryBibleSnapshot


class StoryBibleRepository(Protocol):
    def get(self, project_id: str) -> StoryBibleSnapshot: ...

    def replace(
        self, project_id: str, expected_revision: int, story_bible: StoryBible
    ) -> StoryBibleSnapshot: ...


class WorldEntryIdGenerator(Protocol):
    def __call__(self, project_id: str) -> str: ...
