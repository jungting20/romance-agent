import asyncio
from pathlib import Path

import narrative_analysis_agent
from narrative_analysis_agent import (
    NarrativeAnalysisAgent,
    NarrativeAnalysisConfig,
    SceneAnalysisRequest,
    packaged_prompt_root,
)

from apps.narrative_memory.composition import build_narrative_analysis_agent


def test_backend_builds_only_the_public_agent_facade(tmp_path) -> None:
    agent = build_narrative_analysis_agent(
        model_name="mock",
        prompt_root=tmp_path / "prompts",
        audit_path=tmp_path / "audit.sqlite3",
    )

    assert isinstance(agent, NarrativeAnalysisAgent)
    assert isinstance(agent.config, NarrativeAnalysisConfig)


def test_installed_agent_loads_its_packaged_prompt_through_public_apis(tmp_path) -> None:
    installed_package_root = Path(narrative_analysis_agent.__file__).resolve().parent
    prompt_root = packaged_prompt_root()
    agent = build_narrative_analysis_agent(
        model_name="mock",
        prompt_root=prompt_root,
        audit_path=tmp_path / "audit.sqlite3",
    )

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
    assert prompt_root == installed_package_root / "prompts"
    assert result.snapshot.summary == ""
