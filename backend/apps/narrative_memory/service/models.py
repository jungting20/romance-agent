from dataclasses import dataclass

from narrative_analysis_agent import KnowledgeGraphOutput


@dataclass(frozen=True, slots=True)
class SceneGraphRecord:
    project_id: str
    scene_id: str
    scene_revision: int
    scene_sequence: int
    graph: KnowledgeGraphOutput
