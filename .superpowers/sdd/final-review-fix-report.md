# Final Review Fix Report

## Scope

This remediation resolves the three accepted Important findings from the final
whole-branch review. It changes no HTTP/OpenAPI/frontend behavior and preserves
the existing explicit `NarrativeAnalysisConfig` boundary.

## Finding FBR-I1: installed package prompt omission

- Added setuptools package-data configuration for
  `narrative_analysis_agent/prompts/**/*.md`.
- Added and publicly exported the stdlib-only
  `packaged_prompt_root() -> Path` helper. It points at the package-owned prompt
  directory but does not alter or default `NarrativeAnalysisConfig`.
- Added a focused helper/config test and a backend installed-artifact smoke test.
  The backend test imports the dependency from
  `backend/.venv/lib/python3.13/site-packages`, selects the helper result
  explicitly, and completes an empty-scene facade run.
- Built a wheel, inspected the archive entry
  `narrative_analysis_agent/prompts/scene-analysis/system.md`, extracted it to a
  temporary directory, and loaded prompt `scene-analysis` version 1 through the
  public helper and facade-owned prompt loader. No wheel, `build/`, or
  `*.egg-info` artifact remains in the worktree.

## Finding FBR-I2: missing backend facade consumption use case

- Added `AnalyzeSceneUseCase` with immutable `AnalyzeSceneInput` and
  `AnalyzedScene` application types.
- The injected `SceneAnalysisFacade` protocol exposes only the public
  `SceneAnalysisRequest`/`SceneAnalysisResult` method.
- The use case constructs the exact public request, invokes the facade, and maps
  the returned snapshot exactly once through `to_domain_scene_snapshot()`.
- Public `NarrativeAnalysisError` becomes the sanitized
  `SceneAnalysisApplicationError`; only public `run_id` is preserved and the
  original cause/context is suppressed from the rendered traceback.
- Fake-agent tests verify exact known entity/place conversion, immutable input,
  backend-domain result use, success `run_id`, and absence of provider secrets
  and causes. Composition still returns the public `NarrativeAnalysisAgent`.

## Finding FBR-I3: stale domain ownership text

- Changed only the stale Narrative Memory invariant phrase from the backend
  translation boundary to the independent narrative analysis agent's
  deterministic translation boundary.
- Domain semantics and dependency directions are unchanged, so
  `docs/domains/README.md` remains unchanged.

## TDD evidence

- RED: `llm-agent/tests/unit/test_config.py` failed to import
  `packaged_prompt_root`.
- RED: backend focused collection failed because both the installed helper and
  `scene_analysis_use_case` module were absent.
- GREEN: llm-agent focused prompt/config tests: 27 passed.
- GREEN: backend focused composition/result/use-case tests: 6 passed.

## Verification

- `llm-agent: mise exec -- uv lock --check` -- passed, 108 packages resolved.
- `llm-agent: mise exec -- uv run pytest -m "not live"` -- 203 passed,
  1 live test deselected.
- `llm-agent: mise exec -- uv run ruff check .` -- passed.
- `llm-agent: mise exec -- uv run ruff format --check .` -- 31 files formatted.
- `backend: mise exec -- uv sync --dev` -- rebuilt and installed the local
  package into backend site-packages.
- `backend: mise exec -- uv lock --check` -- passed, 114 packages resolved.
- `backend: mise exec -- uv run pytest` -- 173 passed.
- `backend: mise exec -- uv run ruff check .` -- passed.
- `backend: mise exec -- uv run ruff format --check .` -- known pre-existing
  failure only: four Story Bible files would be reformatted; 59 files formatted.
- Affected backend format check -- 3 files formatted.
- Backend-private-agent and llm-agent-to-backend boundary scans -- empty.
- `git diff --check` -- passed.
- Build/egg-info worktree artifact scan -- empty.
- OpenAPI, frontend, `docs/domains/README.md`, and Story Bible diffs -- empty.

## Changed paths

- `llm-agent/pyproject.toml`
- `llm-agent/src/narrative_analysis_agent/config.py`
- `llm-agent/src/narrative_analysis_agent/__init__.py`
- `llm-agent/tests/unit/test_config.py`
- `llm-agent/docs/llm-agent-coding-rules.md`
- `backend/apps/narrative_memory/service/scene_analysis_use_case.py`
- `backend/tests/narrative_memory/test_scene_analysis_use_case.py`
- `backend/tests/narrative_memory/test_agent_composition.py`
- `backend/README.md`
- `backend/docs/backend-coding-rules.md`
- `docs/domains/narrative-memory.md`
- `.superpowers/sdd/final-review-fix-report.md`

## Remaining concern

The full backend Ruff format check remains red only for the four pre-existing
Story Bible files named in the verification output. They are outside this
remediation's ownership and were not changed. No other concern remains within
the assigned scope.

## FBR-I2-context follow-up

- Root cause: raising the sanitized application error with `from None` inside
  the active `except NarrativeAnalysisError` handler suppressed traceback
  rendering but retained the public error in `__context__`; that error could
  retain a provider exception as its cause.
- Fix: capture only public `run_id` inside the handler, return the unchanged
  success result from `else`, and raise the new application error after leaving
  the active exception handler. The sanitized error now has both `__cause__`
  and `__context__` set to `None`.
- RED: the focused use-case test failed with
  `NarrativeAnalysisError('SECRET_PROVIDER_MESSAGE')` in `__context__`.
- GREEN: `mise exec -- uv run pytest tests/narrative_memory/test_scene_analysis_use_case.py -v`
  -- 3 passed.
- `backend: mise exec -- uv run pytest` -- 173 passed.
- `backend: mise exec -- uv run ruff check .` -- passed.
- Affected format check for the use-case implementation and test -- 2 files
  formatted.
- The llm-agent suite was not rerun because this follow-up changed no llm-agent
  code, package metadata, prompts, or tests.
