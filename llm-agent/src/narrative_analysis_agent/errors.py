class NarrativeAnalysisError(RuntimeError):
    def __init__(self, message: str, *, run_id: str | None = None) -> None:
        super().__init__(message)
        self.run_id = run_id


class AnalysisConfigurationError(NarrativeAnalysisError):
    pass


class PromptLoadError(NarrativeAnalysisError):
    pass


class ProviderUnavailableError(NarrativeAnalysisError):
    pass


class InvalidExtractionError(NarrativeAnalysisError):
    pass


class AnalysisAuditError(NarrativeAnalysisError):
    pass
