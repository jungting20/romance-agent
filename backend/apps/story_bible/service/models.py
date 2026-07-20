from dataclasses import dataclass

from apps.story_bible.domain.models import StoryBible


@dataclass(frozen=True)
class StoryBibleSnapshot:
    story_bible: StoryBible
    revision: int
