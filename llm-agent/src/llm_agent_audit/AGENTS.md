# LLM Agent Audit Instructions

## Scope and ownership

This package owns only provider-independent audit events, audit ports, and the
audited runner decorator shared by LLM agent packages. It does not own files,
databases, loggers, retention, encryption, or access policies.

## Boundaries

- Do not accept credentials as input or expose them through audit metadata.
- Keep provider-specific inspection isolated in `inspection.py`.
- Keep sensitive prompt and response content opt-in through the audit sink.
- Do not import behavior from an owning agent package.

## Verification

Run the common `llm-agent/AGENTS.md` verification commands.
