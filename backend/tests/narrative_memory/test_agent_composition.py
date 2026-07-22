from narrative_analysis_agent import NarrativeAnalysisAgent, NarrativeAnalysisConfig

from apps.narrative_memory.composition import build_narrative_analysis_agent


def test_backend_builds_only_the_public_agent_facade(tmp_path) -> None:
    agent = build_narrative_analysis_agent(
        model_name="mock",
        prompt_root=tmp_path / "prompts",
        audit_path=tmp_path / "audit.sqlite3",
    )

    assert isinstance(agent, NarrativeAnalysisAgent)
    assert isinstance(agent.config, NarrativeAnalysisConfig)
