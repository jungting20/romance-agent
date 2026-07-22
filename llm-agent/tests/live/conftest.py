import os
from pathlib import Path

import pytest

from narrative_analysis_agent import (
    KnownIdentity,
    NarrativeAnalysisAgent,
    SceneAnalysisRequest,
    packaged_prompt_path,
)

ROOT = Path(__file__).parents[3]


def _identity(identity_key: str, name: str) -> KnownIdentity:
    return KnownIdentity(
        identity_key=identity_key,
        normalized_name=name,
        display_name=name,
    )


@pytest.fixture
def scene_request() -> SceneAnalysisRequest:
    return SceneAnalysisRequest(
        project_id="project-live-evaluation",
        scene_id="scene-reunion-at-haedam",
        scene_revision=1,
        scene_sequence=7,
        text=(ROOT / "input.txt").read_text().rstrip("\n"),
        known_entities=(
            _identity("character:han-seoyun", "한서윤"),
            _identity("character:cha-mina", "차민아"),
            _identity("character:kang-dohyeon", "강도현"),
            _identity("character:yun-taegyeong", "윤태경"),
        ),
        known_places=(_identity("place:haedam-bookstore", "해담서점"),),
    )


@pytest.fixture
def live_agent() -> NarrativeAnalysisAgent:
    if os.environ.get("RUN_LLM_LIVE_TESTS") != "1":
        pytest.skip("set RUN_LLM_LIVE_TESTS=1 to run live provider tests")

    model_name = os.environ.get("NARRATIVE_LLM_MODEL", "").strip()
    if not model_name:
        pytest.skip("set NARRATIVE_LLM_MODEL to run live provider tests")

    return NarrativeAnalysisAgent(model_name, prompt_path=packaged_prompt_path())
