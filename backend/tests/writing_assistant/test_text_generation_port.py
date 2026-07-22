import asyncio

from apps.writing_assistant.service.text_generation_port import TextGenerationPort


class StubTextGenerator:
    async def generate_text(self, prompt: str) -> str:
        return prompt


def test_text_generator_implements_async_port_contract() -> None:
    generator: TextGenerationPort = StubTextGenerator()

    assert asyncio.run(generator.generate_text("prompt")) == "prompt"
