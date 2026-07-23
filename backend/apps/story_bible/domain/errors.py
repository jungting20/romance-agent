from typing import Literal


class InvalidDomainValueError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


class WorldEntryChangeError(ValueError):
    def __init__(
        self,
        reason: Literal["duplicate_update", "unknown_update", "addition_id_conflict"],
        entry_id: str,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.entry_id = entry_id


class CharacterNotFoundError(ValueError):
    def __init__(self, character_id: str) -> None:
        super().__init__(character_id)
        self.character_id = character_id
