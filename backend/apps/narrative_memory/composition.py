from pathlib import Path

from narrative_analysis_agent import NarrativeAnalysisAgent


def build_narrative_analysis_agent(*, model_name: str, prompt_path: Path) -> NarrativeAnalysisAgent:
    return NarrativeAnalysisAgent(model_name, prompt_path=prompt_path)
