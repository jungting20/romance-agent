# Narrative Analysis Agent Coding Rules

## Public contracts

- Use immutable, strict Pydantic models as both structured model output and the
  public result representation.
- Use tuples for public collections and reject unknown model fields.
- Keep model-provider details behind `NarrativeAnalysisAgent`.

## Analysis pipeline

- Split scene text into at most 300-character chunks with 50-character overlap.
- Process chunks serially in numeric order and call the model once per chunk.
- Read the packaged or caller-supplied UTF-8 prompt for each analysis request.
- Keep evidence offsets relative to the containing chunk and preserve extraction
  order without cross-chunk translation, merging, or deduplication.
- Sanitize provider and structured-output failures. Return no partial result
  after any chunk failure and propagate asynchronous cancellation unchanged.
- Do not add audit storage, provider retries, prompt registries or metadata,
  durable IDs, candidate status, scene snapshot assembly, or automatic backend
  persistence.

## Tests

- Keep ordinary tests deterministic and network-free by injecting an agent
  runner at the Pydantic AI model-call boundary.
- Mark real-provider evaluations with `live`; require explicit opt-in and keep
  them outside the default test run.
- Live assertions verify required extraction semantics and chunk-relative
  evidence slices without logging prompts, credentials, or provider responses.
