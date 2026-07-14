from typing import Protocol, runtime_checkable


@runtime_checkable
class TextGenerationPort(Protocol):
    async def generate_text(self, prompt: str) -> str: ...
