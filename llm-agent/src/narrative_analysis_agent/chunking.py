from dataclasses import dataclass

MAX_CHUNK_CHARACTERS = 300
CHUNK_OVERLAP_CHARACTERS = 50
CHUNK_STRIDE_CHARACTERS = MAX_CHUNK_CHARACTERS - CHUNK_OVERLAP_CHARACTERS


@dataclass(frozen=True, slots=True)
class SceneChunk:
    chunk_id: str
    ordinal: int
    start_offset: int
    end_offset: int
    text: str


def chunk_scene(
    scene_id: str,
    scene_revision: int,
    text: str,
) -> tuple[SceneChunk, ...]:
    chunks: list[SceneChunk] = []
    for ordinal, start in enumerate(range(0, len(text), CHUNK_STRIDE_CHARACTERS)):
        end = min(start + MAX_CHUNK_CHARACTERS, len(text))
        chunk_text = text[start:end]
        chunks.append(
            SceneChunk(
                chunk_id=f"{scene_id}:r{scene_revision}:{ordinal:04d}",
                ordinal=ordinal,
                start_offset=start,
                end_offset=end,
                text=chunk_text,
            )
        )
        if end == len(text):
            break
    return tuple(chunks)
