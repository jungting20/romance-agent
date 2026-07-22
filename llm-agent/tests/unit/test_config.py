from pathlib import Path

from narrative_analysis_agent import packaged_prompt_root
from narrative_analysis_agent.extraction.prompts import FilePromptRegistry


def test_packaged_prompt_root_loads_the_package_owned_prompt() -> None:
    prompt_root = packaged_prompt_root()

    prompt = FilePromptRegistry(prompt_root).load("scene-analysis")

    assert isinstance(prompt_root, Path)
    assert prompt_root.name == "prompts"
    assert prompt.prompt_id == "scene-analysis"
    assert prompt.version == 1
