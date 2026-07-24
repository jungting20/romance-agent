# Dialogue Generation Agent Coding Rules

## Public contract

- Use immutable, strict Pydantic models for both the request and the structured JSON result.
- Use tuples for public collections and reject unknown fields.
- Keep provider selection, prompt loading, and generation ID creation behind
  `DialogueGenerationAgent`.
- Treat `scene_id`, `generation_id`, `character_id`, `turn_id`, and `information_id` as
  distinct identifier namespaces and validate all returned references against the request.

## Generation pipeline

- Read the packaged or caller-supplied UTF-8 system prompt once per request.
- Allocate one non-empty generation ID per model-call attempt and require the result to return
  that exact ID.
- Send the complete request in one model call without retries, persistence, or cross-agent imports.
- Keep ordinary tests deterministic and network-free by injecting the runner and generation ID
  factory.
- Sanitize prompt, provider, structured-output, and semantic-validation failures. Return no result
  that fails reference or information-flow validation, and propagate asynchronous cancellation.

## Information safety

- Treat every `forbidden_information` item as unavailable for disclosure in the current request;
  `revealable_when` documents a future condition and is not evaluated by the agent.
- Require every forbidden `information_id` in `metadata.information_flow.withheld` and reject any
  reported forbidden-information violation or forbidden ID marked as revealed.
- Reject exact case-insensitive forbidden-content occurrences in dialogue lines as a deterministic
  final guard. The system prompt remains responsible for semantic paraphrase and inference safety.
- Require revealed and withheld information references, dialogue turn references, and character
  references to resolve to the request.

## Non-responsibilities

- Do not read or write Manuscript, Story Bible, Narrative Memory, databases, or files other than
  the configured prompt.
- Follow the [common agent audit boundary](llm-agent-coding-rules.md) for audit events. Do not add
  agent-specific concrete audit storage, credential or prompt/provider-response logging, retries,
  automatic prompt registries, or backend/API integration.
- Do not decide that a future disclosure condition has been met; callers must create a later
  request with an updated information boundary.
