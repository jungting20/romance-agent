from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    prompt_id: str
    version: int
    result_schema: str
    content_hash: str
    raw_bytes: bytes
    body: str


class PromptRegistryPort(Protocol):
    def load(self, prompt_id: str) -> PromptDefinition: ...
