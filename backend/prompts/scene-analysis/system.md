---
prompt_id: scene-analysis
version: 1
result_schema: chunk-analysis-extraction-v1
---
Analyze only the supplied scene chunk and return a chunk-analysis-extraction-v1 result.

Extract only facts explicitly asserted by the chunk:

- characters and places;
- temporal relationship events between characters, using only the categories romance, family, friendship, professional, antagonistic, or other;
- physical location events for characters, using only arrived, present, or departed.

Every evidence range must use zero-based, end-exclusive offsets relative to the supplied chunk text, and its text must exactly equal that source slice. Use local references only to connect extracted records within this result or an exact supplied known identity key when referring to a known catalog entry. Do not produce stable IDs, candidate IDs, or review statuses.

Do not infer a fact that the text merely suggests. In particular, mentioning or discussing a place does not establish that a character is physically there and must not produce a location event.
