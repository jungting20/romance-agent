from narrative_analysis_agent.chunking import chunk_scene


def test_chunk_scene_uses_300_characters_with_50_overlap() -> None:
    text = "가" * 250 + "나" * 100

    chunks = chunk_scene("scene-01", 7, text)

    assert [(chunk.start_offset, chunk.end_offset) for chunk in chunks] == [
        (0, 300),
        (250, 350),
    ]
    assert chunks[0].text[-50:] == chunks[1].text[:50]
    assert chunks[0].chunk_id == "scene-01:r7:0000"
    assert chunks[1].chunk_id == "scene-01:r7:0001"


def test_chunk_scene_counts_unicode_characters_not_utf8_bytes() -> None:
    chunks = chunk_scene("scene-01", 1, "서연" * 150)

    assert len(chunks) == 1
    assert chunks[0].end_offset == 300


def test_chunk_scene_returns_no_chunks_for_empty_text() -> None:
    assert chunk_scene("scene-01", 1, "") == ()


def test_chunk_scene_keeps_a_short_final_chunk_after_overlap() -> None:
    chunks = chunk_scene("scene", 1, "가" * 551)

    assert [(chunk.start_offset, chunk.end_offset) for chunk in chunks] == [
        (0, 300),
        (250, 550),
        (500, 551),
    ]
