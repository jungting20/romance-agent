from dataclasses import dataclass
from pathlib import Path


def packaged_prompt_root() -> Path:
    return Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True, slots=True)
class NarrativeAnalysisConfig:
    model_name: str
    prompt_root: Path
    audit_path: Path
