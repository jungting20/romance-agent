from unittest.mock import patch

import pytest

from infrastructure.llm.pydantic_ai_scene_analysis import PydanticAISceneAnalysisAgent
from infrastructure.llm.scene_analysis_factory import (
    ModelConfigurationError,
    create_scene_analysis_agent,
)
from infrastructure.llm.scripted_scene_analysis import ScriptedSceneAnalysisAgent


def test_factory_requires_non_blank_model_configuration() -> None:
    with pytest.raises(ModelConfigurationError, match="NARRATIVE_LLM_MODEL"):
        create_scene_analysis_agent(environ={})
    with pytest.raises(ModelConfigurationError, match="NARRATIVE_LLM_MODEL"):
        create_scene_analysis_agent(environ={"NARRATIVE_LLM_MODEL": "   "})


def test_factory_uses_exact_mock_sentinel() -> None:
    assert isinstance(
        create_scene_analysis_agent(environ={"NARRATIVE_LLM_MODEL": "mock"}),
        ScriptedSceneAnalysisAgent,
    )


def test_factory_prefers_explicit_model_and_defers_provider_check() -> None:
    with patch("infrastructure.llm.pydantic_ai_scene_analysis.Agent") as constructor:
        adapter = create_scene_analysis_agent(
            model_name="  openai:example  ",
            environ={"NARRATIVE_LLM_MODEL": "mock"},
        )

    assert isinstance(adapter, PydanticAISceneAnalysisAgent)
    constructor.assert_called_once_with(
        "openai:example",
        output_type=adapter.output_type,
        retries=0,
        defer_model_check=True,
    )


def test_factory_does_not_treat_other_case_as_mock() -> None:
    with patch("infrastructure.llm.pydantic_ai_scene_analysis.Agent") as constructor:
        adapter = create_scene_analysis_agent(model_name="Mock", environ={})

    assert isinstance(adapter, PydanticAISceneAnalysisAgent)
    constructor.assert_called_once()
