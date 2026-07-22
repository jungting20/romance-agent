import os
from pathlib import Path

import pytest

from narrative_analysis_agent import (
    KnownIdentity,
    NarrativeAnalysisAgent,
    NarrativeAnalysisConfig,
    SceneAnalysisRequest,
)

ROOT = Path(__file__).parents[3]
PROMPT_ROOT = ROOT / "llm-agent/src/narrative_analysis_agent/prompts"


def _build_scene_request() -> SceneAnalysisRequest:
    return SceneAnalysisRequest(
        project_id="project-live-evaluation",
        scene_id="scene-reunion-at-haedam",
        scene_revision=1,
        scene_sequence=7,
        text=(ROOT / "input.txt").read_text().rstrip("\n"),
        known_entities=(
            KnownIdentity("character:han-seoyun", "한서윤", "한서윤"),
            KnownIdentity("character:cha-mina", "차민아", "차민아"),
            KnownIdentity("character:kang-dohyeon", "강도현", "강도현"),
            KnownIdentity("character:yun-taegyeong", "윤태경", "윤태경"),
        ),
        known_places=(KnownIdentity("place:haedam-bookstore", "해담서점", "해담서점"),),
    )


@pytest.fixture
def scene_request() -> SceneAnalysisRequest:
    return _build_scene_request()


@pytest.fixture
def live_agent(tmp_path: Path) -> NarrativeAnalysisAgent:
    if os.environ.get("RUN_LLM_LIVE_TESTS") != "1":
        pytest.skip("set RUN_LLM_LIVE_TESTS=1 to run live provider tests")

    model_name = os.environ.get("NARRATIVE_LLM_MODEL", "").strip()
    if not model_name:
        pytest.skip("set NARRATIVE_LLM_MODEL to run live provider tests")

    return NarrativeAnalysisAgent(
        NarrativeAnalysisConfig(
            model_name=model_name,
            prompt_root=PROMPT_ROOT,
            audit_path=tmp_path / "scene-analysis-live-audit.sqlite3",
        )
    )
