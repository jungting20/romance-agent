# Story Bible Domain Boundary Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the existing Story Bible backend so domain invariants, application orchestration, persistence, HTTP translation, and runtime composition have explicit owners while preserving every current API and JSON-file behavior.

**Architecture:** Introduce validated immutable Story Bible domain values and an aggregate-owned world-entry transition. Keep commands, results, errors, and ports in the application layer; make the file repository an adapter over those boundaries; and move environment-dependent construction out of the router.

**Tech Stack:** Python 3.13, dataclasses, typing `Protocol` and `Literal`, FastAPI, Pydantic 2, pytest, Ruff, project-scoped JSON files.

## Global Constraints

- Preserve `GET /projects/{projectId}/story-bible` and `PUT /projects/{projectId}/story-bible/world-entries`, including `getStoryBible` and `saveWorldEntries` operation IDs.
- Preserve every current request and response field, alias, status code, error code, field path, and Korean user-facing message.
- Preserve `story-bible.json`, `schemaVersion: 1`, all JSON keys and list ordering, exact revision semantics, path safety, locking, same-directory temporary writes, `fsync`, atomic replacement, and owned-temp cleanup.
- Do not modify `docs/api/openapi.yaml`, `docs/domains/story-bible.md`, `docs/domains/README.md`, frontend files, or unrelated backend applications.
- Do not add confirmed-event features, scene-context selection, a database, ORM, remote storage, async persistence, generic base layers, or a general DI container.
- Follow `backend/AGENTS.md`, `backend/docs/backend-coding-rules.md`, and `docs/superpowers/specs/2026-07-20-story-bible-domain-boundary-refactor-design.md`.

## File Map

- Create `backend/apps/story_bible/domain/{__init__,errors,models}.py` for domain invariants and aggregate behavior.
- Create `backend/apps/story_bible/service/{commands,errors,models,ports}.py` for application values, failures, results, and ports.
- Modify `backend/apps/story_bible/service/story_bible.py` to contain orchestration only.
- Modify `backend/apps/story_bible/repository/story_bible.py` to import authoritative domain/application types and translate invalid stored domain values.
- Create `backend/apps/story_bible/composition.py` for environment, repository, UUID generator, and service construction.
- Modify `backend/apps/story_bible/router/story_bible.py` and `backend/main.py` to use the composition boundary.
- Create `backend/tests/story_bible/test_domain.py`; modify the existing Story Bible service, repository, and API tests.

---

### Task 1: Create the Validated Domain Model

**Files:**
- Create: `backend/apps/story_bible/domain/__init__.py`
- Create: `backend/apps/story_bible/domain/errors.py`
- Create: `backend/apps/story_bible/domain/models.py`
- Create: `backend/tests/story_bible/test_domain.py`

**Interfaces:**
- Consumes: no service, router, schema, repository, environment, or provider types.
- Produces: `WorldEntryKind`, `Character`, `WorldEntry`, `StoryBible`, `InvalidDomainValueError`, `WorldEntryChangeError`.
- Produces: `StoryBible.apply_world_entry_changes(*, updates: tuple[WorldEntry, ...], additions: tuple[WorldEntry, ...]) -> StoryBible`.

- [ ] **Step 1: Write failing construction tests**

Create `test_domain.py` with helpers and these cases:

```python
import pytest

from apps.story_bible.domain.errors import InvalidDomainValueError
from apps.story_bible.domain.models import Character, StoryBible, WorldEntry


def character(identifier: str = "character-1") -> Character:
    return Character(identifier, "서윤", "protagonist", "욕망", "숨은 감정")


def entry(identifier: str = "world-1") -> WorldEntry:
    return WorldEntry(identifier, "place", " 온실 ", " 마지막 만남의 장소 ")


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (lambda: character(""), "id"),
        (lambda: Character("character-1", "", "protagonist", "", ""), "name"),
        (lambda: WorldEntry("", "place", "제목", "설명"), "id"),
        (lambda: WorldEntry("world-1", "invalid", "제목", "설명"), "kind"),
        (lambda: WorldEntry("world-1", "place", "  ", "설명"), "title"),
        (lambda: WorldEntry("world-1", "place", "제목", "\n"), "description"),
        (lambda: StoryBible("", (), ()), "project_id"),
    ],
)
def test_domain_values_reject_invalid_fields(factory: object, field: str) -> None:
    with pytest.raises(InvalidDomainValueError) as raised:
        factory()  # type: ignore[operator]

    assert raised.value.field == field


def test_world_entry_normalizes_owned_text() -> None:
    result = entry()

    assert result.title == "온실"
    assert result.description == "마지막 만남의 장소"


def test_story_bible_rejects_duplicate_character_ids() -> None:
    with pytest.raises(InvalidDomainValueError) as raised:
        StoryBible("project-1", (character(), character()), ())

    assert raised.value.field == "characters"


def test_story_bible_rejects_duplicate_world_entry_ids() -> None:
    with pytest.raises(InvalidDomainValueError) as raised:
        StoryBible("project-1", (), (entry(), entry()))

    assert raised.value.field == "world_entries"
```

- [ ] **Step 2: Verify the tests fail before implementation**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/story_bible/test_domain.py -v
```

Expected: collection fails because `apps.story_bible.domain` does not exist.

- [ ] **Step 3: Implement domain errors and immutable values**

Create `domain/errors.py`:

```python
from typing import Literal


class InvalidDomainValueError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


class WorldEntryChangeError(ValueError):
    def __init__(
        self,
        reason: Literal["duplicate_update", "unknown_update", "addition_id_conflict"],
        entry_id: str,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.entry_id = entry_id
```

Create `domain/models.py`:

```python
from dataclasses import dataclass
from typing import Literal

from apps.story_bible.domain.errors import InvalidDomainValueError, WorldEntryChangeError

WorldEntryKind = Literal["place", "object", "rule"]


def _require_nonempty(value: str, field: str) -> None:
    if not value:
        raise InvalidDomainValueError(field, f"{field} must not be empty")


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    role: Literal["protagonist"]
    desire: str
    hidden_feeling: str

    def __post_init__(self) -> None:
        _require_nonempty(self.id, "id")
        _require_nonempty(self.name, "name")
        if self.role != "protagonist":
            raise InvalidDomainValueError("role", "Unsupported character role")


@dataclass(frozen=True)
class WorldEntry:
    id: str
    kind: WorldEntryKind
    title: str
    description: str

    def __post_init__(self) -> None:
        _require_nonempty(self.id, "id")
        if self.kind not in {"place", "object", "rule"}:
            raise InvalidDomainValueError("kind", "Unsupported world entry kind")
        title = self.title.strip()
        description = self.description.strip()
        if not title:
            raise InvalidDomainValueError("title", "World entry title must not be blank")
        if not description:
            raise InvalidDomainValueError("description", "World entry description must not be blank")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)


@dataclass(frozen=True)
class StoryBible:
    project_id: str
    characters: tuple[Character, ...]
    world_entries: tuple[WorldEntry, ...]

    def __post_init__(self) -> None:
        _require_nonempty(self.project_id, "project_id")
        if len({item.id for item in self.characters}) != len(self.characters):
            raise InvalidDomainValueError("characters", "Character IDs must be unique")
        if len({item.id for item in self.world_entries}) != len(self.world_entries):
            raise InvalidDomainValueError("world_entries", "World entry IDs must be unique")

    def apply_world_entry_changes(
        self,
        *,
        updates: tuple[WorldEntry, ...],
        additions: tuple[WorldEntry, ...],
    ) -> "StoryBible":
        updates_by_id = {item.id: item for item in updates}
        if len(updates_by_id) != len(updates):
            duplicate = next(
                item.id for item in updates if sum(value.id == item.id for value in updates) > 1
            )
            raise WorldEntryChangeError("duplicate_update", duplicate)
        existing_ids = {item.id for item in self.world_entries}
        unknown = next((item.id for item in updates if item.id not in existing_ids), None)
        if unknown is not None:
            raise WorldEntryChangeError("unknown_update", unknown)
        used_ids = set(existing_ids)
        for addition in additions:
            if addition.id in used_ids:
                raise WorldEntryChangeError("addition_id_conflict", addition.id)
            used_ids.add(addition.id)
        entries = tuple(updates_by_id.get(item.id, item) for item in self.world_entries)
        return StoryBible(self.project_id, self.characters, entries + additions)
```

Create an empty `domain/__init__.py`; do not recreate a mixed re-export namespace.

- [ ] **Step 4: Add aggregate-transition tests**

Append:

```python
from apps.story_bible.domain.errors import WorldEntryChangeError


def test_apply_changes_preserves_omitted_state_and_order() -> None:
    omitted = WorldEntry("world-2", "object", "반지", "약속의 증표")
    current = StoryBible("project-1", (character(),), (entry(), omitted))
    updated = WorldEntry("world-1", "rule", "새 규칙", "새 설명")
    added = WorldEntry("world-3", "place", "정원", "재회의 장소")

    result = current.apply_world_entry_changes(updates=(updated,), additions=(added,))

    assert result.characters is current.characters
    assert result.world_entries == (updated, omitted, added)
    assert current.world_entries == (entry(), omitted)


@pytest.mark.parametrize(
    ("updates", "additions", "reason"),
    [
        ((entry(), entry()), (), "duplicate_update"),
        ((WorldEntry("missing", "place", "제목", "설명"),), (), "unknown_update"),
        ((), (entry(),), "addition_id_conflict"),
    ],
)
def test_apply_changes_rejects_invalid_identifiers(
    updates: tuple[WorldEntry, ...],
    additions: tuple[WorldEntry, ...],
    reason: str,
) -> None:
    current = StoryBible("project-1", (character(),), (entry(),))

    with pytest.raises(WorldEntryChangeError) as raised:
        current.apply_world_entry_changes(updates=updates, additions=additions)

    assert raised.value.reason == reason
    assert current.world_entries == (entry(),)
```

- [ ] **Step 5: Run focused verification and commit**

```sh
mise exec -- uv run pytest tests/story_bible/test_domain.py -v
mise exec -- uv run ruff check apps/story_bible/domain tests/story_bible/test_domain.py
mise exec -- uv run ruff format --check apps/story_bible/domain tests/story_bible/test_domain.py
git add backend/apps/story_bible/domain backend/tests/story_bible/test_domain.py
git commit -m "refactor(backend): model story bible domain invariants"
```

Expected: tests pass, both Ruff commands exit 0, and only Task 1 files are committed.

### Task 2: Separate and Refactor the Application Boundary

**Files:**
- Create: `backend/apps/story_bible/service/commands.py`
- Create: `backend/apps/story_bible/service/errors.py`
- Create: `backend/apps/story_bible/service/models.py`
- Create: `backend/apps/story_bible/service/ports.py`
- Modify: `backend/apps/story_bible/service/story_bible.py`
- Modify: `backend/tests/story_bible/test_service.py`

**Interfaces:**
- Consumes: Task 1 domain types and errors.
- Produces commands: `WorldEntryUpdate`, `WorldEntryAddition`, `SaveWorldEntriesCommand`, `FieldError`.
- Produces result: `StoryBibleSnapshot(story_bible: StoryBible, revision: int)`.
- Produces ports: `StoryBibleRepository` and callable `WorldEntryIdGenerator`.
- Produces existing application errors and preserves both public service methods.

- [ ] **Step 1: Move test imports to the intended modules and add a domain-error translation case**

Update `test_service.py` imports, then add:

```python
@pytest.mark.parametrize(
    ("addition", "expected_error"),
    [
        (WorldEntryAddition("place", "  ", "설명"), FieldError("additions[0].title", "제목을 입력해 주세요.")),
        (
            WorldEntryAddition("place", "제목", "\n"),
            FieldError("additions[0].description", "설명을 입력해 주세요."),
        ),
    ],
)
def test_save_translates_domain_errors_to_existing_field_errors(
    addition: WorldEntryAddition,
    expected_error: FieldError,
) -> None:
    repository = RecordingRepository()

    with pytest.raises(InvalidWorldEntriesError) as raised:
        StoryBibleService(repository, lambda _project_id: "world-2").save_world_entries(
            "silver-garden", command(additions=(addition,))
        )

    assert raised.value.message == "세계관 항목을 확인해 주세요."
    assert raised.value.field_errors == (expected_error,)
    assert repository.replace_calls == []
```

- [ ] **Step 2: Verify the intended imports fail**

```sh
mise exec -- uv run pytest tests/story_bible/test_service.py -v
```

Expected: collection fails because the extracted service modules do not exist.

- [ ] **Step 3: Extract application values, results, errors, and ports**

Move the existing frozen command dataclasses unchanged to `service/commands.py`. Move `StoryBibleNotFoundError`, `StoryBibleRevisionConflictError`, `InvalidWorldEntriesError`, and `StoryBiblePersistenceError` unchanged to `service/errors.py`.

Create `service/models.py`:

```python
from dataclasses import dataclass

from apps.story_bible.domain.models import StoryBible


@dataclass(frozen=True)
class StoryBibleSnapshot:
    story_bible: StoryBible
    revision: int
```

Create `service/ports.py`:

```python
from typing import Protocol

from apps.story_bible.domain.models import StoryBible
from apps.story_bible.service.models import StoryBibleSnapshot


class StoryBibleRepository(Protocol):
    def get(self, project_id: str) -> StoryBibleSnapshot: ...

    def replace(
        self, project_id: str, expected_revision: int, story_bible: StoryBible
    ) -> StoryBibleSnapshot: ...


class WorldEntryIdGenerator(Protocol):
    def __call__(self, project_id: str) -> str: ...
```

- [ ] **Step 4: Make the service coordinate domain behavior**

Remove domain dataclasses, commands, errors, snapshot, and port definitions from `service/story_bible.py`. Import their new owners. Retain exact revision, empty-command, duplicate-ID, unknown-ID, and message-precedence behavior.

Construct validated update/addition `WorldEntry` values, accumulating `InvalidDomainValueError` as existing `FieldError` values. Use this exact field-message map:

```python
_FIELD_MESSAGES = {
    "id": "수정할 세계관 항목을 선택해 주세요.",
    "kind": "세계관 항목 종류를 확인해 주세요.",
    "title": "제목을 입력해 주세요.",
    "description": "설명을 입력해 주세요.",
}
```

After all validation and collision-free ID allocation, delegate the state transition and persist once:

```python
replacement = current.story_bible.apply_world_entry_changes(
    updates=tuple(validated_updates),
    additions=tuple(validated_additions),
)
return self._repository.replace(project_id, command.expected_revision, replacement)
```

Type the constructor dependency as `WorldEntryIdGenerator`. Allow the repository's compare-and-replace conflict to propagate unchanged.

- [ ] **Step 5: Run the application tests and commit**

```sh
mise exec -- uv run pytest tests/story_bible/test_service.py -v
mise exec -- uv run ruff check apps/story_bible/service tests/story_bible/test_service.py
mise exec -- uv run ruff format --check apps/story_bible/service tests/story_bible/test_service.py
git add backend/apps/story_bible/service backend/tests/story_bible/test_service.py
git commit -m "refactor(backend): separate story bible application boundary"
```

Expected: all existing and new service tests pass, Ruff exits 0, and the commit contains only Task 2 files.

### Task 3: Rewire the File Repository

**Files:**
- Modify: `backend/apps/story_bible/repository/story_bible.py`
- Modify: `backend/tests/story_bible/test_file_repository.py`

**Interfaces:**
- Consumes: domain models, application errors, and `StoryBibleSnapshot` from their Task 1–2 owners.
- Produces: `FileStoryBibleRepository` structurally satisfying `StoryBibleRepository`.
- Preserves: schema version 1, codec keys, paths, locking, revision comparison, and durable replacement.

- [ ] **Step 1: Update test imports and add malformed stored-domain values**

Move test imports to their new owners. Add one document with an empty character ID and one with a blank world-entry title to the existing malformed-document parametrization. Each document must contain the complete current envelope and must raise `StoryBiblePersistenceError`, not `InvalidDomainValueError`.

Use these payload fragments inside otherwise valid documents:

```python
{"id": "", "name": "서윤", "role": "protagonist", "desire": "", "hiddenFeeling": ""}
{"id": "world-1", "kind": "place", "title": "  ", "description": "설명"}
```

- [ ] **Step 2: Verify repository tests fail on stale ownership or leaked domain errors**

```sh
mise exec -- uv run pytest tests/story_bible/test_file_repository.py -v
```

Expected: FAIL until repository imports and decode-error translation are updated.

- [ ] **Step 3: Correct repository dependencies and translation**

Replace imports from `service.story_bible` with:

```python
from apps.story_bible.domain.errors import InvalidDomainValueError
from apps.story_bible.domain.models import Character, StoryBible, WorldEntry
from apps.story_bible.service.errors import (
    StoryBibleNotFoundError,
    StoryBiblePersistenceError,
    StoryBibleRevisionConflictError,
)
from apps.story_bible.service.models import StoryBibleSnapshot
```

At `_read`, translate `InvalidDomainValueError` alongside malformed JSON, type, key, and value failures into `StoryBiblePersistenceError("Could not read Story Bible")`. Preserve the earlier `except StoryBiblePersistenceError: raise` branch. Keep strict keys, stored-project equality, positive revision, role/kind checks, path safety, locking, and atomic-write code behaviorally unchanged.

- [ ] **Step 4: Prove representation and durability compatibility**

```sh
mise exec -- uv run pytest \
  tests/story_bible/test_file_repository.py::test_get_reloads_same_snapshot \
  tests/story_bible/test_file_repository.py::test_replace_writes_expected_envelope_and_reloads \
  tests/story_bible/test_file_repository.py::test_failed_write_cleans_owned_temp_and_preserves_canonical_bytes \
  -v
mise exec -- uv run pytest tests/story_bible/test_file_repository.py -v
mise exec -- uv run ruff check apps/story_bible/repository tests/story_bible/test_file_repository.py
mise exec -- uv run ruff format --check apps/story_bible/repository tests/story_bible/test_file_repository.py
```

Expected: unchanged JSON envelope and revision assertions pass; failure bytes remain unchanged; all repository tests and Ruff checks pass.

- [ ] **Step 5: Commit the repository boundary**

```sh
git add backend/apps/story_bible/repository/story_bible.py backend/tests/story_bible/test_file_repository.py
git commit -m "refactor(backend): invert story bible repository dependencies"
```

### Task 4: Isolate Runtime Composition from HTTP Translation

**Files:**
- Create: `backend/apps/story_bible/composition.py`
- Modify: `backend/apps/story_bible/router/story_bible.py`
- Modify: `backend/main.py`
- Modify: `backend/tests/story_bible/test_api.py`

**Interfaces:**
- Consumes: `FileStoryBibleRepository`, `StoryBibleService`, extracted commands/errors/results.
- Produces: `get_story_bible_service() -> StoryBibleService` and `StoryBibleDependencyError`.
- Preserves: every route decorator, response schema, operation ID, and HTTP error mapping.

- [ ] **Step 1: Update API test imports and assert the router has no repository composition**

Import `get_story_bible_service` and `StoryBibleDependencyError` from `apps.story_bible.composition`; import domain/application types from their authoritative modules. Patch repository construction through the composition module in the existing dependency-failure test.

Add:

```python
def test_router_does_not_own_runtime_repository_composition() -> None:
    assert not hasattr(router_module, "FileStoryBibleRepository")
```

- [ ] **Step 2: Verify the new composition import fails**

```sh
mise exec -- uv run pytest tests/story_bible/test_api.py -v
```

Expected: collection fails because `apps.story_bible.composition` does not exist.

- [ ] **Step 3: Create the composition module**

Create `composition.py`:

```python
import logging
import os
import uuid
from pathlib import Path

from apps.story_bible.repository.story_bible import FileStoryBibleRepository
from apps.story_bible.service.story_bible import StoryBibleService

logger = logging.getLogger(__name__)


class StoryBibleDependencyError(Exception):
    """The Story Bible service could not be composed for a request."""


def _new_world_entry_id(project_id: str) -> str:
    return f"{project_id}-world-{uuid.uuid4().hex}"


def get_story_bible_service() -> StoryBibleService:
    try:
        repository = FileStoryBibleRepository(Path(os.environ["ROMANCE_AGENT_DATA_ROOT"]))
        return StoryBibleService(repository, _new_world_entry_id)
    except Exception as error:
        logger.exception("Could not compose Story Bible service")
        raise StoryBibleDependencyError from error
```

The catch remains only at the explicit composition boundary, where it adds context and translates dependency-construction failure.

- [ ] **Step 4: Reduce the router and update the global handler import**

Remove environment, UUID, `Path`, concrete repository, dependency-error, and provider definitions from `router/story_bible.py`. Import the provider from composition, commands from `service.commands`, errors from `service.errors`, snapshot from `service.models`, and service from `service.story_bible`. Preserve route functions and response conversion byte-for-byte except for import-driven formatting.

Update `backend/main.py` to import `StoryBibleDependencyError` from `apps.story_bible.composition`. Do not change its 500 response.

- [ ] **Step 5: Verify the complete HTTP boundary and commit**

```sh
mise exec -- uv run pytest tests/story_bible/test_api.py -v
mise exec -- uv run pytest \
  tests/story_bible/test_api.py::test_story_bible_operations_preserve_approved_operation_ids \
  tests/story_bible/test_api.py::test_save_maps_all_request_schema_failures_to_malformed_request \
  tests/story_bible/test_api.py::test_dependency_construction_failure_maps_to_internal_error \
  -v
mise exec -- uv run ruff check apps/story_bible/composition.py apps/story_bible/router/story_bible.py tests/story_bible/test_api.py main.py
mise exec -- uv run ruff format --check apps/story_bible/composition.py apps/story_bible/router/story_bible.py tests/story_bible/test_api.py main.py
git add backend/apps/story_bible/composition.py backend/apps/story_bible/router/story_bible.py backend/tests/story_bible/test_api.py backend/main.py
git commit -m "refactor(backend): isolate story bible composition"
```

Expected: API tests pass with unchanged methods, paths, operation IDs, statuses, and bodies; Ruff exits 0; only Task 4 files are committed.

### Task 5: Verify, Review, and Resolve Findings

**Files:**
- Modify only already assigned Story Bible files when verification or review proves the refactor introduced a defect.
- Do not modify domain contracts, OpenAPI, frontend files, or unrelated backend files.

**Interfaces:**
- Consumes: completed Tasks 1–4.
- Produces: a behavior-preserving backend slice with all accepted review findings resolved.

- [ ] **Step 1: Run focused and full backend verification**

Run from `backend/`:

```sh
mise exec -- uv run pytest tests/story_bible -v
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: focused and full pytest exit 0; record observed totals; Ruff lint exits 0; Ruff format reports all files formatted, including the previously failing Story Bible service file.

- [ ] **Step 2: Audit the final implementation diff**

From the repository root, record the commit immediately before Task 1 as `implementation_base`, then run:

```sh
git diff --check "$implementation_base"..HEAD
git diff --stat "$implementation_base"..HEAD
git diff "$implementation_base"..HEAD -- backend/apps/story_bible backend/tests/story_bible backend/main.py
git diff "$implementation_base"..HEAD -- docs/api/openapi.yaml docs/domains/story-bible.md docs/domains/README.md frontend
```

Expected: no whitespace errors; the implementation diff contains only assigned backend paths; the final command has no output.

- [ ] **Step 3: Dispatch the required read-only backend review after editing stops**

Assign the repository-scoped `backend-review` agent these entry points: `getStoryBible`, `saveWorldEntries`, `StoryBibleService.save_world_entries`, `StoryBible.apply_world_entry_changes`, and `FileStoryBibleRepository.replace`. Supply Tasks 1–4 commit IDs, all Global Constraints, `docs/domains/story-bible.md`, the unchanged `docs/api/openapi.yaml` revision recorded at implementation start, no accepted deviations, the affected backend paths, and the Step 1 verification commands.

Require evidence-based findings with severity, introduced/pre-existing classification, source location, impact, repair direction, and re-review requirement. The reviewer must not edit files.

- [ ] **Step 4: Resolve every accepted finding**

Return accepted implementation findings to the backend implementation owner when practical. Record concrete main-agent rationale for every rejected finding. After each repair, run the smallest affected test, then all Step 1 commands. Dispatch the same reviewer again for blocking/high fixes or any repair that materially changes reviewed behavior.

Expected: every accepted finding is resolved and every required re-review has no unresolved accepted finding.

- [ ] **Step 5: Record the final handoff**

```sh
git status --short
git log -6 --oneline
```

Report changed files and behavior, implementation commit IDs, focused and full test totals, Ruff results, unchanged OpenAPI revision, why domain documents remained unchanged, reviewer findings and resolutions, and any unrelated pre-existing worktree state. Do not add a no-op final commit. If review repairs changed files, commit only focused repairs:

```sh
git add backend/apps/story_bible backend/tests/story_bible backend/main.py
git commit -m "fix(backend): resolve story bible refactor review"
```
