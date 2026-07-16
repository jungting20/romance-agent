import os
from collections.abc import Mapping

from apps.narrative_memory.service.scene_analysis_ports import SceneAnalysisAgentPort
from infrastructure.llm.pydantic_ai_scene_analysis import PydanticAISceneAnalysisAgent
from infrastructure.llm.scripted_scene_analysis import ScriptedSceneAnalysisAgent


class ModelConfigurationError(ValueError):
    pass


def create_scene_analysis_agent(
    model_name: str | None = None,
    environ: Mapping[str, str] = os.environ,
) -> SceneAnalysisAgentPort:
    configured_name = model_name if model_name is not None else environ.get("NARRATIVE_LLM_MODEL")
    if configured_name is None or not (resolved_name := configured_name.strip()):
        raise ModelConfigurationError("NARRATIVE_LLM_MODEL must be configured")
    if resolved_name == "mock":
        return ScriptedSceneAnalysisAgent()
    return PydanticAISceneAnalysisAgent(resolved_name)
