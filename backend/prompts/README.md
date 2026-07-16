# Narrative Memory prompts

`scene-analysis/system.md` is the editable system prompt for structured scene-chunk extraction. Its front matter declares the prompt ID, positive version, and supported result schema `chunk-analysis-extraction-v1`.

The application selects a model through `NARRATIVE_LLM_MODEL`. Set it to `mock` explicitly for the local scripted mock; other supported provider/model strings select a real Pydantic AI model in the later composition layer.

The stable JSON user message contains:

- `project_id`, `scene_id`, `scene_revision`, and `scene_sequence`;
- `chunk`, with `chunk_id`, numeric `ordinal`, `start_offset`, `end_offset`, `content_hash`, and the exact chunk `text`;
- `known_entities` and `known_places`, each sorted by `identity_key` and containing `identity_key`, `normalized_name`, `display_name`, and `aliases`.

The registry reads the prompt file on every load, so edits take effect without restarting the backend. Whenever any exact byte in a prompt file changes—including metadata, wording, or whitespace—increment its `version`. Reusing a prompt ID and version with different bytes is invalid when the prompt is registered for audit.

From `backend/`, verify prompt loading and rendering with:

```sh
mise exec -- uv run pytest tests/narrative_memory/test_prompt_registry.py -v
```
