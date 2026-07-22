import asyncio
from pathlib import Path

import narrative_analysis_agent
from narrative_analysis_agent import (
    NarrativeAnalysisAgent,
    SceneAnalysisRequest,
    packaged_prompt_path,
)

from apps.narrative_memory.composition import build_narrative_analysis_agent


def test_backend_builds_only_the_public_agent_facade(tmp_path: Path) -> None:
    prompt_path = tmp_path / "system.md"
    prompt_path.write_text("지시", encoding="utf-8")

    agent = build_narrative_analysis_agent(model_name="test", prompt_path=prompt_path)

    assert isinstance(agent, NarrativeAnalysisAgent)
    assert agent.prompt_path == prompt_path


def test_installed_agent_loads_its_packaged_prompt_through_public_apis() -> None:
    installed_package_root = Path(narrative_analysis_agent.__file__).resolve().parent
    prompt_path = packaged_prompt_path()
    agent = build_narrative_analysis_agent(model_name="test", prompt_path=prompt_path)

    result = asyncio.run(
        agent.analyze_scene(
            SceneAnalysisRequest(
                project_id="project-01",
                scene_id="scene-01",
                scene_revision=1,
                scene_sequence=1,
                text="",
            )
        )
    )

    assert installed_package_root.parent.name == "site-packages"
    assert prompt_path == installed_package_root / "prompts" / "scene-analysis" / "system.md"
    assert result.chunks == ()
