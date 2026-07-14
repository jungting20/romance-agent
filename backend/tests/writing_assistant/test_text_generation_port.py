from pydantic_ai import Agent

from apps.writing_assistant.service.text_generation_port import TextGenerationPort


class StubTextGenerator:
    async def generate_text(self, prompt: str) -> str:
        return prompt


def test_text_generator_can_implement_port_structurally() -> None:
    assert isinstance(StubTextGenerator(), TextGenerationPort)


def test_pydantic_ai_is_available() -> None:
    assert Agent.__module__.startswith("pydantic_ai")
