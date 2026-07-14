import asyncio

from pydantic_ai import Agent

from apps.writing_assistant.service.text_generation_port import TextGenerationPort


class StubTextGenerator:
    async def generate_text(self, prompt: str) -> str:
        return prompt


def test_text_generator_implements_async_port_contract() -> None:
    generator: TextGenerationPort = StubTextGenerator()

    assert asyncio.run(generator.generate_text("prompt")) == "prompt"


def test_pydantic_ai_is_available() -> None:
    assert Agent.__module__.startswith("pydantic_ai")
