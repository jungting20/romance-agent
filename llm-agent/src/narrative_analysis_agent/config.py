from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class NarrativeAnalysisConfig:
    model_name: str
    prompt_root: Path
    audit_path: Path
