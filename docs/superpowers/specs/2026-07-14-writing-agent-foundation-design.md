# Writing Agent Foundation Design

## Goal

Create the minimum backend foundation for the Writing Assistant agent and add
Pydantic AI as its agent framework. This change establishes package boundaries
only; it does not expose an API operation or generate a writing suggestion.

## Selected approach

Keep the agent capability inside the existing Writing Assistant bounded
context. Do not introduce a top-level `agent` domain. Separate application and
domain-facing orchestration from external model-provider details.

The alternatives considered were an empty directory scaffold, a complete API
endpoint scaffold, and the selected package scaffold with an outbound model
port. Empty directories would not be tracked by Git and would communicate too
little intent. An endpoint would require a frontend-drafted and main-approved
OpenAPI operation, which is outside this foundation step.

## Package structure

```text
backend/
├── apps/
│   └── writing_assistant/
│       ├── __init__.py
│       ├── router/
│       │   └── __init__.py
│       ├── schemas/
│       │   └── __init__.py
│       ├── service/
│       │   ├── __init__.py
│       │   └── text_generation_port.py
│       └── repository/
│           └── __init__.py
└── infrastructure/
    ├── __init__.py
    └── llm/
        └── __init__.py
```

`text_generation_port.py` defines the outbound dependency needed by a future
Writing Assistant service. It must remain independent of Pydantic AI, FastAPI,
and any specific model provider. The infrastructure package will contain the
future Pydantic AI implementation, but this step does not create a concrete
agent because its prompt, model, dependencies, and structured result have not
yet been designed.

## Dependency

Add the `pydantic-ai` distribution to `backend/pyproject.toml` using `uv`, and
refresh `backend/uv.lock`. Do not configure credentials, select a model, or add
provider-specific packages beyond dependencies resolved by Pydantic AI.

## Boundaries

- Other domains do not call the model port.
- A future application use case gathers Manuscript and Story Bible context and
  passes explicit input to the Writing Assistant service.
- The Writing Assistant service owns suggestion generation rules but never
  mutates Manuscript state.
- Provider SDK usage and Pydantic AI agent construction belong under
  `backend/infrastructure/llm/`.
- No router is registered in `backend/main.py` during this foundation step.

## Domain and API impact

This is a structural foundation that preserves the current Writing Assistant
domain meaning and behavior. Therefore, `docs/domains/writing-assistant.md` does
not require a semantic update. No API operation is introduced, so
`docs/api/openapi.yaml` is unchanged.

## Verification

From `backend/`, run:

```sh
mise exec -- uv sync --dev
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Also verify that `pydantic_ai` imports successfully without instantiating an
agent or making a network request.
