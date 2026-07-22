from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from narrative_analysis_agent.audit.sqlite import SQLiteAgentAudit
from narrative_analysis_agent.config import NarrativeAnalysisConfig
from narrative_analysis_agent.contracts import SceneAnalysisRequest, SceneAnalysisResult
from narrative_analysis_agent.errors import AnalysisAuditError, AnalysisConfigurationError
from narrative_analysis_agent.extraction.agent import (
    PydanticAIChunkAnalyzer,
    ScriptedChunkAnalyzer,
)
from narrative_analysis_agent.extraction.prompts import FilePromptRegistry
from narrative_analysis_agent.orchestrator import SceneAnalysisOrchestrator


class NarrativeAnalysisAgent:
    def __init__(self, config: NarrativeAnalysisConfig) -> None:
        self.config = config
        self._orchestrator = build_orchestrator(config)

    async def analyze_scene(self, request: SceneAnalysisRequest) -> SceneAnalysisResult:
        return await self._orchestrator.analyze_scene(request)


def build_orchestrator(config: NarrativeAnalysisConfig) -> SceneAnalysisOrchestrator:
    if not config.model_name.strip():
        raise AnalysisConfigurationError("scene analysis model must not be blank")

    try:
        analyzer = (
            ScriptedChunkAnalyzer()
            if config.model_name == "mock"
            else PydanticAIChunkAnalyzer(config.model_name)
        )
    except Exception:
        raise AnalysisConfigurationError("unable to configure scene analysis provider") from None

    audit = SQLiteAgentAudit(config.audit_path)
    try:
        audit.initialize()
    except Exception:
        raise AnalysisAuditError("unable to initialize scene analysis audit") from None

    return SceneAnalysisOrchestrator(
        analyzer=analyzer,
        prompt_registry=FilePromptRegistry(config.prompt_root),
        audit=audit,
        run_id_factory=lambda: str(uuid4()),
        clock=lambda: datetime.now(UTC),
        monotonic=monotonic,
    )
