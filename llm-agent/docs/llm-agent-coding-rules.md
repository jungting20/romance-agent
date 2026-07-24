# Narrative Analysis Agent Coding Rules

## Public contracts

- Use immutable, strict Pydantic models as both structured model output and the
  public result representation.
- Use tuples for public collections and reject unknown model fields.
- Keep model-provider details behind `NarrativeAnalysisAgent`.

## Common agent audit boundary

- Narrative Analysis and Dialogue Generation use the same `llm_agent_audit`
  `AuditAttemptStarted`/`AuditAttemptFinished` event model, `AgentAuditSink`
  port, and `AuditedAgentRunner` recording-runner decorator when an
  application composes auditing.
- Keep the wrapped provider runner responsible only for the model call. The
  separately composed recording decorator is responsible for audit event
  construction and required append behavior; neither agent package selects a
  concrete sink or audit storage.
- Configure the agent name and prompt identity on the recording decorator.
  Agent workflows open one decorated audit run and invoke one attempt per model
  call without constructing or passing audit run IDs or `PromptIdentity`.
- Do not send audit events to normal application logs and do not record
  credentials, prompt text, provider responses, or encryption keys outside the
  explicitly opt-in sensitive payload path owned by the application sink.

## Analysis pipeline

- Read the configured Narrative Memory SQLite file once at the start of each
  analysis through URI read-only mode, close the connection before returning,
  and use an empty v2 graph only when the project has no current record.
- Reject missing or inaccessible files, invalid hashes, malformed payloads,
  v1 payloads, and unknown schemas before any provider call. Do not create,
  migrate, repair, or write the database.
- Split scene text into at most 300-character chunks with 50-character overlap.
- Process chunks serially in numeric order and call the model once per chunk.
- Provide the same project graph snapshot to every chunk in one analysis. Do
  not accumulate earlier chunk output into later chunk input.
- Read the packaged or caller-supplied UTF-8 prompt for each analysis request.
- Require non-empty evidence and first-mention strings to occur verbatim in the
  containing chunk. Do not create scene-absolute evidence records.
- Preserve extraction order without cross-chunk ID translation, merging, or
  deduplication. Treat extraction IDs as chunk-local, never durable identities.
- Sanitize graph-read, provider, and structured-output failures. Return no
  partial result after any chunk failure and propagate asynchronous cancellation
  unchanged.
- Do not add concrete audit storage, credentials or prompt/provider-response
  logging, provider retries, prompt registries or metadata, database writes,
  durable IDs, candidate status, scene snapshot assembly, or automatic backend
  persistence. Concrete sinks and normal application logging are outside this
  package boundary.

## Tests

- Keep ordinary tests deterministic and network-free by injecting an agent
  runner at the Pydantic AI model-call boundary.
- Mark real-provider evaluations with `live`; require explicit opt-in and keep
  them outside the default test run.
- Live assertions verify required extraction semantics and chunk-relative
  evidence slices without logging prompts, credentials, or provider responses.
