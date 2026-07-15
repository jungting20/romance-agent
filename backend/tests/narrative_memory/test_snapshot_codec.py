from dataclasses import FrozenInstanceError

import pytest

from apps.narrative_memory.service.models import (
    Evidence,
    ProjectRelationshipSnapshot,
)


def test_empty_project_snapshot_is_version_zero() -> None:
    snapshot = ProjectRelationshipSnapshot.empty("project-01")

    assert snapshot.project_id == "project-01"
    assert snapshot.snapshot_version == 0
    assert snapshot.relationship_events == ()
    assert snapshot.location_events == ()


def test_evidence_is_immutable() -> None:
    evidence = Evidence(
        chunk_id="scene-01:r1:0000",
        start_offset=0,
        end_offset=3,
        text="서연은",
    )

    with pytest.raises(FrozenInstanceError):
        evidence.text = "민준은"  # type: ignore[misc]
