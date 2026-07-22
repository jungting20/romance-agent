from pathlib import Path

from narrative_analysis_agent import NarrativeAnalysisAgent, NarrativeAnalysisConfig


def build_narrative_analysis_agent(
    *, model_name: str, prompt_root: Path, audit_path: Path
) -> NarrativeAnalysisAgent:
    return NarrativeAnalysisAgent(
        NarrativeAnalysisConfig(
            model_name=model_name,
            prompt_root=prompt_root,
            audit_path=audit_path,
        )
    )
