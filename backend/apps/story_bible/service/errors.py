from apps.story_bible.service.commands import FieldError


class StoryBibleNotFoundError(Exception):
    """The requested project's Story Bible does not exist."""


class StoryBibleRevisionConflictError(Exception):
    """The expected revision does not exactly match the stored revision."""


class InvalidWorldEntriesError(Exception):
    def __init__(self, message: str, field_errors: tuple[FieldError, ...]) -> None:
        super().__init__(message)
        self.message = message
        self.field_errors = field_errors


class StoryBiblePersistenceError(Exception):
    """Stored Story Bible data cannot be safely read or written."""
