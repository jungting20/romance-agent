import os
import sqlite3
from pathlib import Path

import pytest

from narrative_analysis_agent import (
    NarrativeAnalysisAgent,
    SceneAnalysisRequest,
    packaged_prompt_path,
)

ROOT = Path(__file__).parents[3]


@pytest.fixture
def scene_request() -> SceneAnalysisRequest:
    return SceneAnalysisRequest(
        project_id="project-live-evaluation",
        scene_id="scene-reunion-at-haedam",
        scene_revision=1,
        scene_sequence=7,
        text=(ROOT / "input.txt").read_text().rstrip("\n"),
    )


@pytest.fixture
def live_agent(tmp_path: Path) -> NarrativeAnalysisAgent:
    if os.environ.get("RUN_LLM_LIVE_TESTS") != "1":
        pytest.skip("set RUN_LLM_LIVE_TESTS=1 to run live provider tests")

    model_name = os.environ.get("NARRATIVE_LLM_MODEL", "").strip()
    if not model_name:
        pytest.skip("set NARRATIVE_LLM_MODEL to run live provider tests")

    graph_path = tmp_path / "narrative-memory.sqlite3"
    with sqlite3.connect(graph_path) as connection:
        connection.executescript(
            """
            CREATE TABLE project_snapshots (
                project_id TEXT NOT NULL,
                snapshot_version INTEGER NOT NULL,
                schema_version TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                payload BLOB NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, snapshot_version)
            );
            CREATE TABLE current_project_snapshots (
                project_id TEXT PRIMARY KEY,
                snapshot_version INTEGER NOT NULL
            );
            """
        )

    return NarrativeAnalysisAgent(
        model_name,
        project_graph_path=graph_path,
        prompt_path=packaged_prompt_path(),
    )
