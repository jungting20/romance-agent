from pathlib import Path

from narrative_analysis_agent import NarrativeAnalysisAgent

from apps.narrative_memory.repository.sqlite_snapshot_repository import (
    SQLiteSnapshotRepository,
)
from apps.narrative_memory.service.scene_analysis_use_case import AnalyzeSceneUseCase


def build_narrative_analysis_agent(
    *,
    model_name: str,
    prompt_path: Path,
    project_graph_path: Path,
) -> NarrativeAnalysisAgent:
    return NarrativeAnalysisAgent(
        model_name,
        prompt_path=prompt_path,
        project_graph_path=project_graph_path,
    )


def build_analyze_scene_use_case(
    *,
    model_name: str,
    prompt_path: Path,
    project_graph_path: Path,
) -> AnalyzeSceneUseCase:
    repository = SQLiteSnapshotRepository(project_graph_path)
    repository.initialize()
    agent = build_narrative_analysis_agent(
        model_name=model_name,
        prompt_path=prompt_path,
        project_graph_path=project_graph_path,
    )
    return AnalyzeSceneUseCase(agent, repository)
