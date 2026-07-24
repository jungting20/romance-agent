# Task 4 — backend JSONL audit sink report

## TDD evidence

- RED: `mise exec -- uv run pytest tests/infrastructure/test_jsonl_agent_audit.py -v`
  initially failed during collection with the expected
  `ModuleNotFoundError: infrastructure.audit.jsonl_agent_audit`.
- GREEN: added the owner-only JSONL sink, immutable configuration validation,
  AES-256-GCM envelope with event AAD, and the `cryptography>=45,<47` runtime
  dependency. The focused suite then passed all 11 tests.

## Verification evidence

From `backend/`:

```text
mise exec -- uv lock
  Resolved 114 packages; cryptography locked at 46.0.7.

mise exec -- uv run pytest tests/infrastructure/test_jsonl_agent_audit.py -v
  11 passed

mise exec -- uv run ruff check infrastructure/audit tests/infrastructure/test_jsonl_agent_audit.py
  All checks passed

mise exec -- uv run ruff format --check infrastructure/audit tests/infrastructure/test_jsonl_agent_audit.py
  3 files already formatted

mise exec -- uv run pytest
  316 passed

mise exec -- uv run ruff check .
  All checks passed

mise exec -- uv run ruff format --check .
  63 files already formatted

git diff --check
  passed
```

## T4-I1 credential allowlist fix

- RED: added `test_metadata_serialization_uses_only_the_allowed_model_settings`.
  It supplied `headers` with an Authorization bearer, `auth`, `base_url`, and
  `endpoint` values alongside `temperature` and `max_tokens`; the prior
  blacklist implementation failed by retaining the credential-bearing settings.
- GREEN: metadata serialization now uses the exact Task 1 positive allowlist:
  `temperature`, `max_tokens`, `top_p`, `seed`, and `timeout`. The regression
  test proves only the two supplied allowed settings remain and every secret
  string is absent.
- Verification: focused audit suite `12 passed`; full backend suite `317
  passed`; scoped and full Ruff checks/format checks passed; `git diff --check`
  passed.

## Self-review

- Metadata is one canonical JSON line with `allow_nan=False`; credential-like
  model-setting names are omitted.
- Metadata and sensitive handlers are instance-local, INFO-only, non-propagating,
  midnight-rotating, and removed/closed by `close()`.
- The audit directory is enforced as `0700`; emitted files are enforced as
  `0600`.
- Raw content remains disabled by default. When enabled, it requires a nonblank
  key ID and exactly 32 key bytes; sensitive content appears only inside an
  AES-256-GCM ciphertext envelope authenticated by event AAD.
- No domain contract or OpenAPI behavior changed.
