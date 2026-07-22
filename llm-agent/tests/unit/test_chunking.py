from hashlib import sha256

from narrative_analysis_agent.chunking import (
    CHUNK_OVERLAP_CHARACTERS,
    CHUNK_STRIDE_CHARACTERS,
    MAX_CHUNK_CHARACTERS,
    chunk_scene,
)


def test_chunk_scene_uses_canonical_300_50_250_boundaries_and_stable_ids() -> None:
    text = "x" * 551

    chunks = chunk_scene("scene-01", 2, text)

    assert (MAX_CHUNK_CHARACTERS, CHUNK_OVERLAP_CHARACTERS, CHUNK_STRIDE_CHARACTERS) == (
        300,
        50,
        250,
    )
    assert [
        (chunk.chunk_id, chunk.ordinal, chunk.start_offset, chunk.end_offset) for chunk in chunks
    ] == [
        ("scene-01:r2:0000", 0, 0, 300),
        ("scene-01:r2:0001", 1, 250, 550),
        ("scene-01:r2:0002", 2, 500, 551),
    ]
    assert chunks[0].text[-50:] == chunks[1].text[:50]
    assert chunks[1].text[-50:] == chunks[2].text[:50]
    assert chunks[0].content_hash == f"sha256:{sha256(text[:300].encode('utf-8')).hexdigest()}"


def test_chunk_scene_returns_no_chunks_for_empty_text() -> None:
    assert chunk_scene("scene-01", 1, "") == ()
