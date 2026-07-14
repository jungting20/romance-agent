from typing import Protocol


class TextGenerationPort(Protocol):
    async def generate_text(self, prompt: str) -> str: ...
