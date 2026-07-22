from dataclasses import dataclass
from hashlib import sha256

MAX_CHUNK_CHARACTERS = 300
CHUNK_OVERLAP_CHARACTERS = 50
CHUNK_STRIDE_CHARACTERS = MAX_CHUNK_CHARACTERS - CHUNK_OVERLAP_CHARACTERS


@dataclass(frozen=True, slots=True)
class SceneChunk:
    chunk_id: str
    scene_id: str
    manuscript_revision: int
    ordinal: int
    start_offset: int
    end_offset: int
    content_hash: str
    text: str


def chunk_scene(
    scene_id: str,
    manuscript_revision: int,
    text: str,
) -> tuple[SceneChunk, ...]:
    chunks: list[SceneChunk] = []
    for ordinal, start in enumerate(range(0, len(text), CHUNK_STRIDE_CHARACTERS)):
        end = min(start + MAX_CHUNK_CHARACTERS, len(text))
        chunk_text = text[start:end]
        chunks.append(
            SceneChunk(
                chunk_id=f"{scene_id}:r{manuscript_revision}:{ordinal:04d}",
                scene_id=scene_id,
                manuscript_revision=manuscript_revision,
                ordinal=ordinal,
                start_offset=start,
                end_offset=end,
                content_hash=f"sha256:{sha256(chunk_text.encode('utf-8')).hexdigest()}",
                text=chunk_text,
            )
        )
        if end == len(text):
            break
    return tuple(chunks)
