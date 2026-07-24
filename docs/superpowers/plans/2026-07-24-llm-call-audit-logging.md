# LLM 호출 감사 로깅 공통 모듈 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 두 LLM agent의 실제 provider 호출을 하나의 공통 runner에서 감사하고 backend 소유의 격리된 JSONL 로그에 안전하게 기록한다.

**Architecture:** `llm_agent_audit` package가 immutable event, sink port, Pydantic AI result inspector와 `AuditedAgentRunner`를 제공한다. 두 agent는 기존 injected runner를 이 decorator로 감싸고 기존 prompt·검증·public result를 유지한다. backend는 non-propagating 전용 logger, file rotation, AES-256-GCM과 owner-only 파일 정책을 구현하고 composition에서 sink를 주입한다.

**Tech Stack:** Python 3.13, dataclasses, asyncio, Pydantic AI 2.x, Python `logging.handlers.TimedRotatingFileHandler`, `cryptography` AESGCM, pytest, ruff, uv/mise

## Global Constraints

- 작업 브랜치는 `feature/llm-호출-감사-로깅`이며 전용 worktree `/Users/in05908_mac/Documents/romance-agent-llm-audit`에서만 편집한다.
- authoritative design은 `docs/superpowers/specs/2026-07-24-llm-call-audit-logging-design.md`다.
- persistence는 backend 소유 전용 JSONL audit logging이며 SQLite를 추가하지 않는다.
- raw capture 기본값은 disabled, metadata retention 기본값은 30일, encrypted content retention 기본값은 7일이다.
- raw sensitive payload 전체만 AES-256-GCM으로 암호화하고 metadata는 plaintext로 기록한다.
- configured audit sink는 fail-closed이며 cancellation terminal audit만 best-effort다.
- Narrative Analysis와 Dialogue Generation의 public request/result, prompt bytes, 호출 횟수, retry 없음, 검증 규칙과 정제된 public error를 변경하지 않는다.
- credential, provider URL/details, headers, exception repr/traceback, prompt와 원고 원문을 metadata 또는 일반 logger/telemetry에 전달하지 않는다.
- frontend, consumer-facing API, OpenAPI, audit viewer, external telemetry와 `docs/domains/*` 변경은 범위 밖이다.
- 기존 테스트의 `RecordingRunner`는 호출 관찰용 test double로 유지하고 운영 audit sink로 재사용하지 않는다.
- 모든 커밋 메시지는 한글로 작성한다.

---

## File Structure

### Create

- `llm-agent/src/llm_agent_audit/AGENTS.md`: 공통 package 범위와 storage 비소유 규칙
- `llm-agent/src/llm_agent_audit/__init__.py`: public audit contract exports
- `llm-agent/src/llm_agent_audit/events.py`: immutable metadata, usage, start/terminal event와 sensitive payload
- `llm-agent/src/llm_agent_audit/inspection.py`: model config sanitization과 Pydantic AI result inspection
- `llm-agent/src/llm_agent_audit/runner.py`: sink port, no-op sink, fail-closed audited decorator
- `llm-agent/tests/unit/test_audited_runner.py`: 공통 성공·실패·취소·민감 원문·sink failure 계약
- `backend/infrastructure/audit/jsonl_agent_audit.py`: 전용 JSONL logger, rotation, permission, AES-GCM adapter
- `backend/tests/infrastructure/test_jsonl_agent_audit.py`: 격리·retention·암호화·plaintext 부재 테스트
- `backend/docs/llm-audit-logging.md`: 실행 애플리케이션 소유 정책과 구성 예시

### Modify

- `llm-agent/src/narrative_analysis_agent/agent.py`: 공통 decorator와 run/attempt/prompt metadata 적용
- `llm-agent/src/dialogue_generation_agent/agent.py`: 동일 공통 decorator 적용
- `llm-agent/src/narrative_analysis_agent/AGENTS.md`: 개별 storage 금지와 공통 port 허용 경계
- `llm-agent/src/dialogue_generation_agent/AGENTS.md`: 개별 storage 금지와 공통 port 허용 경계
- `llm-agent/tests/unit/test_agent.py`: Narrative audit integration 회귀
- `llm-agent/tests/unit/test_dialogue_generation_agent.py`: Dialogue audit integration 회귀
- `llm-agent/docs/llm-agent-coding-rules.md`: 공통 audit contract와 민감정보 규칙
- `llm-agent/docs/dialogue-generation-agent-coding-rules.md`: Dialogue의 공통 경계 사용 규칙
- `backend/infrastructure/audit/__init__.py`: JSONL adapter public exports
- `backend/apps/narrative_memory/composition.py`: application-owned sink 주입
- `backend/tests/narrative_memory/test_agent_composition.py`: sink 전달 회귀
- `backend/docs/backend-coding-rules.md`: JSONL audit ownership 링크와 일반 telemetry 격리 규칙
- `backend/README.md`: 구조와 구성 예시
- `backend/pyproject.toml`: direct `cryptography` dependency
- `backend/uv.lock`: dependency lock 갱신

---

### Task 1: 공통 감사 계약과 AuditedAgentRunner

**Files:**
- Create: `llm-agent/src/llm_agent_audit/AGENTS.md`
- Create: `llm-agent/src/llm_agent_audit/__init__.py`
- Create: `llm-agent/src/llm_agent_audit/events.py`
- Create: `llm-agent/src/llm_agent_audit/inspection.py`
- Create: `llm-agent/src/llm_agent_audit/runner.py`
- Create: `llm-agent/tests/unit/test_audited_runner.py`

**Interfaces:**
- Consumes: wrapped runner `async run(user_prompt: str, *, instructions: str) -> ResultT`
- Produces: `AgentAuditSink`, `NoopAgentAuditSink`, `AuditedAgentRunner`, `AuditAttemptStarted`, `AuditAttemptFinished`, `SensitiveAuditPayload`, `ModelConfiguration`, `PromptIdentity`, `TokenUsage`, `sanitized_model_configuration()`

- [ ] **Step 1: 공통 package 지침과 실패하는 event/runner 테스트 작성**

`llm-agent/src/llm_agent_audit/AGENTS.md`에는 이 package가 provider-independent audit event/port/decorator만 소유하고 file/DB/logger/retention/encryption/access policy를 소유하지 않으며 credential을 입력으로 받지 않는다고 명시한다.

`llm-agent/tests/unit/test_audited_runner.py`에 deterministic clock/ID와 recording sink를 만들고 다음 공개 동작을 테스트한다.

```python
@dataclass
class FakeResult:
    output: FakeOutput
    response: ModelResponse
    usage: RunUsage


class RecordingSink:
    def __init__(self, *, capture_sensitive_content: bool = False) -> None:
        self.capture_sensitive_content = capture_sensitive_content
        self.records: list[tuple[AuditEvent, SensitiveAuditPayload | None]] = []

    async def append(
        self,
        event: AuditEvent,
        sensitive: SensitiveAuditPayload | None = None,
    ) -> None:
        self.records.append((event, sensitive))


def test_audited_runner_records_success_without_sensitive_content_by_default() -> None:
    sink = RecordingSink()
    runner = _audited_runner(sink=sink, result=_result())

    result = asyncio.run(
        runner.run(
            "user secret",
            instructions="system secret",
            run_id="run-1",
            prompt=PromptIdentity.from_text("dialogue-generation.system", 1, "system secret"),
            validate=lambda output: None,
        )
    )

    assert result.output.value == "validated"
    assert [type(record[0]) for record in sink.records] == [
        AuditAttemptStarted,
        AuditAttemptFinished,
    ]
    assert sink.records[0][1] is None
    assert sink.records[1][1] is None
    terminal = cast(AuditAttemptFinished, sink.records[1][0])
    assert terminal.status == "success"
    assert terminal.usage == TokenUsage(input_tokens=11, output_tokens=7)
    assert terminal.duration_ms == 250.0


def test_audited_runner_passes_sensitive_payload_only_when_sink_requests_it() -> None:
    sink = RecordingSink(capture_sensitive_content=True)
    runner = _audited_runner(sink=sink, result=_result())

    asyncio.run(
        runner.run(
            "user secret",
            instructions="system secret",
            run_id="run-1",
            prompt=PromptIdentity.from_text("dialogue-generation.system", 1, "system secret"),
            validate=lambda output: None,
        )
    )

    sensitive = sink.records[-1][1]
    assert sensitive is not None
    assert sensitive.system_prompt == "system secret"
    assert sensitive.user_prompt == "user secret"
    assert sensitive.raw_response_json is not None
    assert sensitive.validated_output_json == b'{"value":"validated"}'
```

같은 파일에 다음 경우를 각각 독립 테스트로 추가한다.

- provider exception은 `failure/model_call_failed` terminal event를 남기고 원 예외를 재전파한다.
- validator `ValueError`는 `failure/output_validation_failed`이며 validated output은 없다.
- cancellation은 `cancelled/cancelled` terminal event 기록을 시도하고 그대로 재전파한다.
- start append 실패는 wrapped runner call count가 0이고 `AgentAuditWriteError`다.
- success terminal append 실패는 결과를 반환하지 않고 `AgentAuditWriteError`다.
- cancellation terminal append 실패는 cancellation을 가리지 않는다.
- prompt hash는 exact UTF-8 bytes의 `sha256:<hex>`다.
- model settings의 `api_key`, `headers`, `base_url`은 제외되고 `temperature`, `max_tokens`, `top_p`, `seed`, `timeout`의 scalar 값만 남는다.

- [ ] **Step 2: focused test를 실행해 RED 확인**

Run:

```sh
cd llm-agent
mise exec -- uv run pytest tests/unit/test_audited_runner.py -v
```

Expected: `ModuleNotFoundError: No module named 'llm_agent_audit'`.

- [ ] **Step 3: immutable event와 inspector 구현**

`events.py`에 frozen/slots dataclass를 정의한다. field names와 types는 아래를 그대로 사용한다.

```python
type AuditStatus = Literal["success", "failure", "cancelled"]
type ModelSettingValue = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class PromptIdentity:
    prompt_id: str
    version: int
    content_hash: str

    @classmethod
    def from_text(cls, prompt_id: str, version: int, text: str) -> PromptIdentity:
        digest = sha256(text.encode("utf-8")).hexdigest()
        return cls(prompt_id=prompt_id, version=version, content_hash=f"sha256:{digest}")


@dataclass(frozen=True, slots=True)
class ModelConfiguration:
    requested_model: str
    requested_provider: str | None
    settings: tuple[tuple[str, ModelSettingValue], ...] = ()


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    details: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class AuditAttemptStarted:
    schema_version: Literal["llm-agent-audit-v1"]
    event_type: Literal["attempt_started"]
    agent_name: str
    run_id: str
    attempt_id: str
    model: ModelConfiguration
    prompt: PromptIdentity
    started_at: datetime


@dataclass(frozen=True, slots=True)
class SanitizedAuditError:
    code: Literal["model_call_failed", "output_validation_failed", "cancelled"]
    message: str


@dataclass(frozen=True, slots=True)
class AuditAttemptFinished:
    schema_version: Literal["llm-agent-audit-v1"]
    event_type: Literal["attempt_finished"]
    agent_name: str
    run_id: str
    attempt_id: str
    model: ModelConfiguration
    prompt: PromptIdentity
    started_at: datetime
    ended_at: datetime
    duration_ms: float
    status: AuditStatus
    actual_provider: str | None
    actual_model: str | None
    usage: TokenUsage | None
    error: SanitizedAuditError | None


@dataclass(frozen=True, slots=True)
class SensitiveAuditPayload:
    system_prompt: str
    user_prompt: str
    raw_response_json: bytes | None
    validated_output_json: bytes | None
```

`inspection.py`는 Pydantic AI `ModelResponse`, `RunUsage`, `ModelMessagesTypeAdapter`와 Pydantic `BaseModel`만 알고 다음 결과를 반환한다.

```python
@dataclass(frozen=True, slots=True)
class InspectedResult:
    actual_provider: str | None
    actual_model: str | None
    usage: TokenUsage | None
    raw_response_json: bytes | None
    validated_output_json: bytes


def sanitized_model_configuration(model: Model | str) -> ModelConfiguration:
    if isinstance(model, str):
        provider, separator, requested_model = model.partition(":")
        return ModelConfiguration(
            requested_model=requested_model if separator else model,
            requested_provider=provider if separator else None,
        )
    settings = tuple(
        sorted(
            (key, value)
            for key, value in (model.settings or {}).items()
            if key in {"temperature", "max_tokens", "top_p", "seed", "timeout"}
            and (value is None or isinstance(value, str | int | float | bool))
        )
    )
    return ModelConfiguration(model.model_name, model.system, settings)
```

`inspect_result(result)`는 없는 optional attribute를 `None`으로 취급하고, nonnegative integer usage만 복사하며, response 한 개를 `ModelMessagesTypeAdapter.dump_json([response])`로 직렬화하고, `BaseModel` output은 `model_dump_json().encode()`로 직렬화한다.

- [ ] **Step 4: fail-closed AuditedAgentRunner 구현**

`runner.py`에는 다음 protocol과 API를 구현한다.

```python
class AgentAuditSink(Protocol):
    capture_sensitive_content: bool

    async def append(
        self,
        event: AuditEvent,
        sensitive: SensitiveAuditPayload | None = None,
    ) -> None: ...


class NoopAgentAuditSink:
    capture_sensitive_content = False

    async def append(
        self,
        event: AuditEvent,
        sensitive: SensitiveAuditPayload | None = None,
    ) -> None:
        return None
```

`AuditedAgentRunner.__init__`의 exact parameters는 `runner`, keyword-only `agent_name`,
`model`, optional `sink`, `id_factory`, `clock`, `monotonic`이다. `new_run_id() -> str`와
`run(user_prompt, *, instructions, run_id, prompt, validate) -> AgentResult[OutputT]`를 public
methods로 구현한다. ID 기본값은 `run-{uuid4()}`와 `attempt-{uuid4()}`다. UTC wall clock은
timezone-aware `datetime.now(UTC)`, duration은 `time.monotonic()` 차이만 사용한다.
start/success terminal append 실패는 `AgentAuditWriteError("agent audit logging failed") from
None`으로 번역한다. provider와 validator exception은 정제 event 기록 후 원 예외를 bare
`raise`로 재전파한다. cancellation terminal append는 `try/except Exception: pass`로만 보호하고
cancellation을 재전파한다. 어떤 metadata event에도 prompt 또는 exception 문자열을 넣지 않는다.

- [ ] **Step 5: public exports와 focused GREEN 확인**

`__init__.py`에서 Task 1의 public types/functions만 `__all__`로 export한다.

Run:

```sh
cd llm-agent
mise exec -- uv run pytest tests/unit/test_audited_runner.py -v
mise exec -- uv run ruff check src/llm_agent_audit tests/unit/test_audited_runner.py
mise exec -- uv run ruff format --check src/llm_agent_audit tests/unit/test_audited_runner.py
```

Expected: all tests pass and both ruff commands exit 0.

- [ ] **Step 6: Task 1 커밋**

```sh
git add llm-agent/src/llm_agent_audit llm-agent/tests/unit/test_audited_runner.py
git commit -m "기능: 공통 LLM 호출 감사 runner 추가"
```

---

### Task 2: Narrative Analysis Agent 공통 감사 경계 적용

**Files:**
- Modify: `llm-agent/src/narrative_analysis_agent/agent.py`
- Modify: `llm-agent/tests/unit/test_agent.py`

**Interfaces:**
- Consumes: Task 1 `AuditedAgentRunner`, `AgentAuditSink`, `PromptIdentity`, `sanitized_model_configuration`
- Produces: 기존 `NarrativeAnalysisAgent.analyze_scene()` 의미를 보존하는 audited chunk calls

- [ ] **Step 1: Narrative integration 실패 테스트 작성**

기존 `GraphRunner`와 별개로 Task 1과 같은 `RecordingSink`를 사용해 다음을 검증한다.

```python
def test_analyze_scene_uses_one_audit_run_and_one_attempt_per_chunk() -> None:
    sink = RecordingSink()
    runner = GraphRunner()
    agent = NarrativeAnalysisAgent(
        "test-provider:test-model",
        graph_reader=RecordingGraphReader(ProjectKnowledgeGraphSnapshot.empty("project-01")),
        runner=runner,
        audit_sink=sink,
        audit_id_factory=iter(("run-fixed", "attempt-1", "attempt-2", "attempt-3")).__next__,
    )

    asyncio.run(agent.analyze_scene(_request()))

    starts = [event for event, _ in sink.records if isinstance(event, AuditAttemptStarted)]
    assert [event.run_id for event in starts] == ["run-fixed"] * 3
    assert [event.attempt_id for event in starts] == ["attempt-1", "attempt-2", "attempt-3"]
    assert {event.agent_name for event in starts} == {"narrative-analysis"}
    assert {event.prompt.prompt_id for event in starts} == {"narrative-analysis.system"}
```

추가 테스트는 semantic `_validate_output` 실패가 `output_validation_failed`로 감사되고 기존 `NarrativeAnalysisError("scene analysis failed")`와 cause suppression을 유지하는지 확인한다. 기존 prompt JSON equality와 call count assertions는 변경하지 않는다.

- [ ] **Step 2: focused RED 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_agent.py -v`

Expected: constructor가 `audit_sink` 또는 `audit_id_factory`를 아직 받지 않아 FAIL.

- [ ] **Step 3: Narrative agent에 decorator 연결**

다음 상수를 추가한다.

```python
_AGENT_NAME = "narrative-analysis"
_PROMPT_ID = "narrative-analysis.system"
_PROMPT_VERSION = 1
```

constructor는 raw runner를 `AuditedAgentRunner`로 감싸며 `audit_sink`와 test-only deterministic `audit_id_factory` optional keyword를 받는다. `analyze_scene()`은 prompt를 읽은 뒤 `run_id = self._runner.new_run_id()`를 한 번 만들고 한국어 목적 comment를 붙인다. `_analyze_chunks`와 `_analyze_chunk`에 run ID를 전달한다.

`_analyze_chunk`의 provider call과 semantic validation은 한 audited call로 묶는다.

```python
result = await self._runner.run(
    _render_user_prompt(request, existing, chunk),
    instructions=instructions,
    run_id=run_id,
    prompt=PromptIdentity.from_text(_PROMPT_ID, _PROMPT_VERSION, instructions),
    validate=lambda output: _validate_output(output, request, chunk, existing),
)
```

catch 목록에 `AgentAuditWriteError`를 포함하고 기존 cancellation과 sanitized public error를 유지한다. 기존 `_validate_output` 함수 내용과 prompt 파일은 수정하지 않는다.

- [ ] **Step 4: Narrative focused/full package checks**

Run:

```sh
cd llm-agent
mise exec -- uv run pytest tests/unit/test_agent.py tests/integration/test_scene_analysis_offline.py -v
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: 0 failures; 기존 133 baseline tests와 새 tests 모두 통과.

- [ ] **Step 5: Task 2 커밋**

```sh
git add llm-agent/src/narrative_analysis_agent/agent.py llm-agent/tests/unit/test_agent.py
git commit -m "기능: 장면 분석 호출에 공통 감사 적용"
```

---

### Task 3: Dialogue Generation Agent 공통 감사 경계 적용

**Files:**
- Modify: `llm-agent/src/dialogue_generation_agent/agent.py`
- Modify: `llm-agent/tests/unit/test_dialogue_generation_agent.py`

**Interfaces:**
- Consumes: Task 1 common audit exports
- Produces: 기존 `DialogueGenerationAgent.generate_dialogue()` 의미를 보존하는 one-run/one-attempt audited call

- [ ] **Step 1: Dialogue integration 실패 테스트 작성**

```python
def test_generate_dialogue_uses_common_audit_run_separate_from_generation_id() -> None:
    sink = RecordingSink()
    agent = DialogueGenerationAgent(
        "test-provider:test-model",
        runner=RecordingRunner(_output()),
        generation_id_factory=lambda: "generation-attempt-01",
        audit_sink=sink,
        audit_id_factory=iter(("run-fixed", "attempt-fixed")).__next__,
    )

    result = asyncio.run(agent.generate_dialogue(_request()))

    started = next(event for event, _ in sink.records if isinstance(event, AuditAttemptStarted))
    assert started.run_id == "run-fixed"
    assert started.attempt_id == "attempt-fixed"
    assert started.agent_name == "dialogue-generation"
    assert started.prompt.prompt_id == "dialogue-generation.system"
    assert result.scene.generation_id == "generation-attempt-01"
```

추가 테스트는 forbidden-information semantic validation failure가 audit `output_validation_failed`로 끝나고 기존 공개 오류·원문 미노출을 유지하는지 확인한다.

- [ ] **Step 2: focused RED 확인**

Run: `cd llm-agent && mise exec -- uv run pytest tests/unit/test_dialogue_generation_agent.py -v`

Expected: constructor audit keyword 미지원으로 FAIL.

- [ ] **Step 3: Dialogue agent에 같은 decorator 연결**

상수는 아래를 사용한다.

```python
_AGENT_NAME = "dialogue-generation"
_PROMPT_ID = "dialogue-generation.system"
_PROMPT_VERSION = 1
```

constructor에서 raw runner를 Task 1 decorator로 감싼다. `generate_dialogue()`는 system prompt를 읽고 기존 generation ID를 만든 뒤 별도 audit run ID를 한 번 만든다. `_generate`에 audit run ID를 전달하고 기존 `_validate_output`을 audited validator callback 안에서 실행해 success가 semantic validation 이후에만 기록되게 한다.

```python
result = await self._runner.run(
    _render_user_prompt(request, generation_id),
    instructions=instructions,
    run_id=audit_run_id,
    prompt=PromptIdentity.from_text(_PROMPT_ID, _PROMPT_VERSION, instructions),
    validate=lambda output: _validate_output(output, request, generation_id),
)
return result.output
```

`_validate_output`의 호출 중복을 제거하되 함수 내용은 수정하지 않는다. `AgentAuditWriteError`는 기존 `DialogueGenerationError("dialogue generation failed") from None`으로 번역한다. Korean step comments를 새 workflow와 동기화한다.

- [ ] **Step 4: Dialogue focused/full package checks**

Run:

```sh
cd llm-agent
mise exec -- uv run pytest tests/unit/test_dialogue_generation_agent.py tests/integration/test_dialogue_generation_offline.py -v
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .
```

Expected: 0 failures; prompt equality, one-call, forbidden information와 cancellation tests 유지.

- [ ] **Step 5: Task 3 커밋**

```sh
git add llm-agent/src/dialogue_generation_agent/agent.py llm-agent/tests/unit/test_dialogue_generation_agent.py
git commit -m "기능: 대화 생성 호출에 공통 감사 적용"
```

---

### Task 4: backend 전용 JSONL 감사 logger와 AES-GCM adapter

**Files:**
- Create: `backend/infrastructure/audit/jsonl_agent_audit.py`
- Create: `backend/tests/infrastructure/test_jsonl_agent_audit.py`
- Modify: `backend/infrastructure/audit/__init__.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`

**Interfaces:**
- Consumes: Task 1 `AgentAuditSink`, `AuditEvent`, `SensitiveAuditPayload`
- Produces: `AgentAuditLogConfig`, `JsonlAgentAuditSink`, `AgentAuditConfigurationError`

- [ ] **Step 1: dependency와 JSONL adapter 실패 테스트 작성**

`backend/pyproject.toml` runtime dependencies에 `cryptography>=45,<47`을 추가하고 `mise exec -- uv lock`으로 lockfile을 갱신한다.

`backend/tests/infrastructure/test_jsonl_agent_audit.py`에 다음 핵심 tests를 작성한다.

```python
def test_metadata_log_is_owner_only_canonical_jsonl_and_does_not_propagate(tmp_path: Path) -> None:
    config = AgentAuditLogConfig(directory=tmp_path / "private")
    sink = JsonlAgentAuditSink(config)

    asyncio.run(sink.append(_started()))
    sink.close()

    path = config.directory / "llm-audit-metadata.jsonl"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["agent_name"] == "dialogue-generation"
    assert "system secret" not in path.read_text(encoding="utf-8")
    assert stat.S_IMODE(config.directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert sink.metadata_logger.propagate is False


def test_raw_capture_is_disabled_and_sensitive_file_is_not_created(tmp_path: Path) -> None:
    config = AgentAuditLogConfig(directory=tmp_path / "private")
    sink = JsonlAgentAuditSink(config)

    assert sink.capture_sensitive_content is False
    asyncio.run(sink.append(_finished(), _sensitive()))
    sink.close()

    assert not (config.directory / "llm-audit-sensitive.jsonl").exists()


def test_sensitive_log_contains_only_aes_gcm_envelope(tmp_path: Path) -> None:
    config = AgentAuditLogConfig(
        directory=tmp_path / "private",
        capture_sensitive_content=True,
        encryption_key=b"k" * 32,
        encryption_key_id="key-2026-07",
    )
    sink = JsonlAgentAuditSink(config, nonce_factory=lambda size: b"n" * size)

    asyncio.run(sink.append(_finished(), _sensitive()))
    sink.close()

    text = (config.directory / "llm-audit-sensitive.jsonl").read_text(encoding="utf-8")
    payload = json.loads(text)
    assert payload["algorithm"] == "AES-256-GCM"
    assert payload["key_id"] == "key-2026-07"
    assert payload["nonce"] == base64.b64encode(b"n" * 12).decode("ascii")
    assert "system secret" not in text
    assert "user secret" not in text
    assert "validated" not in text
```

추가 tests는 raw enabled인데 32-byte key/key ID가 없으면 configuration error, metadata/sensitive handler `when="midnight"`, backup counts 30/7, logger handler가 다른 logger에 붙지 않음, provider credentials를 포함하지 않는 event serialization을 검증한다.

- [ ] **Step 2: focused RED 확인**

Run:

```sh
cd backend
mise exec -- uv run pytest tests/infrastructure/test_jsonl_agent_audit.py -v
```

Expected: `jsonl_agent_audit` import failure.

- [ ] **Step 3: config와 owner-only rotating handler 구현**

config는 다음 exact fields/defaults를 사용한다.

```python
@dataclass(frozen=True, slots=True)
class AgentAuditLogConfig:
    directory: Path
    capture_sensitive_content: bool = False
    encryption_key: bytes | None = None
    encryption_key_id: str | None = None
    metadata_retention_days: int = 30
    sensitive_retention_days: int = 7
```

`__post_init__`는 두 retention이 positive인지 확인하고 raw enabled일 때 key가 exact 32 bytes이며 nonblank key ID인지 확인한다. `_OwnerOnlyTimedRotatingFileHandler._open()`은 `os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)`과 `os.fdopen(..., encoding="utf-8")`을 사용한다. 두 logger는 unique instance name, level INFO, `propagate=False`, `JsonMessageFormatter("%(message)s")` 없이 message 자체만 쓰는 formatter와 정확히 한 handler만 가진다. sensitive handler는 `delay=True`로 raw disabled/미기록 시 파일을 만들지 않는다.

- [ ] **Step 4: event canonical JSON과 AES-GCM envelope 구현**

`JsonlAgentAuditSink.append()`는 `await asyncio.to_thread(self._append, event, sensitive)`를 호출한다. `_append`는 dataclass를 primitive dict로 변환하고 `json.dumps(..., ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))` 한 줄만 metadata logger에 기록한다.

민감 기록은 `capture_sensitive_content and sensitive is not None`일 때만 수행한다. canonical sensitive JSON bytes를 AESGCM으로 암호화한다.

```python
aad = json.dumps(
    {
        "schema_version": event.schema_version,
        "agent_name": event.agent_name,
        "run_id": event.run_id,
        "attempt_id": event.attempt_id,
    },
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
nonce = self._nonce_factory(12)
ciphertext = self._aesgcm.encrypt(nonce, _sensitive_json(sensitive), aad)
envelope = {
    "schema_version": event.schema_version,
    "agent_name": event.agent_name,
    "run_id": event.run_id,
    "attempt_id": event.attempt_id,
    "algorithm": "AES-256-GCM",
    "key_id": self._config.encryption_key_id,
    "nonce": base64.b64encode(nonce).decode("ascii"),
    "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
}
```

`close()`는 logger에서 handler를 제거한 후 handler를 닫는다. 예외를 log하거나 catch하지 않아 Task 1 fail-closed translation이 작동하게 한다.

- [ ] **Step 5: backend adapter focused checks**

Run:

```sh
cd backend
mise exec -- uv run pytest tests/infrastructure/test_jsonl_agent_audit.py -v
mise exec -- uv run ruff check infrastructure/audit tests/infrastructure/test_jsonl_agent_audit.py
mise exec -- uv run ruff format --check infrastructure/audit tests/infrastructure/test_jsonl_agent_audit.py
```

Expected: all pass; no plaintext sensitive values in either log.

- [ ] **Step 6: Task 4 커밋**

```sh
git add backend/infrastructure/audit backend/tests/infrastructure backend/pyproject.toml backend/uv.lock
git commit -m "기능: 전용 JSONL LLM 감사 로그 추가"
```

---

### Task 5: backend composition과 엔지니어링 문서 동기화

**Files:**
- Modify: `backend/apps/narrative_memory/composition.py`
- Modify: `backend/tests/narrative_memory/test_agent_composition.py`
- Create: `backend/docs/llm-audit-logging.md`
- Modify: `backend/docs/backend-coding-rules.md`
- Modify: `backend/README.md`
- Modify: `llm-agent/src/narrative_analysis_agent/AGENTS.md`
- Modify: `llm-agent/src/dialogue_generation_agent/AGENTS.md`
- Modify: `llm-agent/docs/llm-agent-coding-rules.md`
- Modify: `llm-agent/docs/dialogue-generation-agent-coding-rules.md`

**Interfaces:**
- Consumes: Task 1 `AgentAuditSink`, Task 4 `JsonlAgentAuditSink`
- Produces: optional application-owned sink injection through both Narrative composition builders and durable engineering guidance

- [ ] **Step 1: composition sink 전달 실패 테스트 작성**

기존 recording builder signature와 expected calls를 확장한다.

```python
def test_backend_passes_application_owned_audit_sink_to_public_agent(tmp_path: Path) -> None:
    project_graph_path = tmp_path / "narrative-memory.sqlite3"
    SQLiteSnapshotRepository(project_graph_path).initialize()
    sink = NoopAgentAuditSink()

    agent = composition.build_narrative_analysis_agent(
        model_name="test",
        prompt_path=tmp_path / "system.md",
        project_graph_path=project_graph_path,
        audit_sink=sink,
    )

    assert agent._runner._sink is sink
```

white-box identity assertion은 composition wiring만 검증하며 sink 동작은 Task 1/4 tests가 소유한다. `build_analyze_scene_use_case` recording builder test에도 exact same sink object가 전달되는지 추가한다.

- [ ] **Step 2: focused RED 확인**

Run: `cd backend && mise exec -- uv run pytest tests/narrative_memory/test_agent_composition.py -v`

Expected: builder가 `audit_sink` keyword를 받지 않아 FAIL.

- [ ] **Step 3: composition optional sink injection 구현**

두 builders에 다음 keyword를 추가하고 unchanged object를 agent constructor에 전달한다.

```python
def build_narrative_analysis_agent(
    *,
    model_name: str,
    prompt_path: Path,
    project_graph_path: Path,
    audit_sink: AgentAuditSink | None = None,
) -> NarrativeAnalysisAgent:
    return NarrativeAnalysisAgent(
        model_name,
        prompt_path=prompt_path,
        project_graph_path=project_graph_path,
        audit_sink=audit_sink,
    )
```

`build_analyze_scene_use_case`도 같은 optional keyword를 받아 repository initialization 순서와 동일 path invariant를 바꾸지 않고 전달한다. backend가 sink를 만들지 않으며 호출 application이 Task 4 config/adapter를 구성한다.

- [ ] **Step 4: 문서 경계와 운영 구성 동기화**

`backend/docs/llm-audit-logging.md`에 exact 기본값, 두 파일명, 0700/0600, AES key injection, non-propagation, fail-closed, rotation trigger, key/credential 미기록과 다음 구성 예시를 기록한다.

```python
audit_sink = JsonlAgentAuditSink(
    AgentAuditLogConfig(
        directory=data_root / "private" / "llm-audit",
        capture_sensitive_content=False,
    )
)
use_case = build_analyze_scene_use_case(
    model_name="provider:model",
    prompt_path=packaged_prompt_path(),
    project_graph_path=data_root / "narrative-memory.sqlite3",
    audit_sink=audit_sink,
)
```

raw enabled 예시는 실행 애플리케이션이 이미 획득한 32-byte key와 non-secret key ID를 주입하는 형태만 보이고 environment variable 이름이나 key 문자열을 문서에 넣지 않는다. `backend-coding-rules.md`는 상세 내용을 새 문서로 링크하고 cross-cutting infrastructure ownership만 유지한다. `backend/README.md` 구조 map에 `infrastructure/audit`과 docs 링크를 추가한다.

llm-agent 문서는 “개별 agent audit storage 금지”를 “공통 `llm_agent_audit` port/decorator 사용, concrete storage 금지”로 바꾼다. `llm-agent/docs/llm-agent-coding-rules.md`에 두 agent 공통 event, no credentials, no normal logs, RecordingRunner 분리를 기록한다. Dialogue 문서는 같은 공통 경계만 참조하고 agent-specific storage를 금지한다. domain 문서는 수정하지 않는다.

- [ ] **Step 5: focused와 양쪽 full checks**

Run:

```sh
cd llm-agent
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .

cd ../backend
mise exec -- uv run pytest tests/infrastructure/test_jsonl_agent_audit.py tests/narrative_memory/test_agent_composition.py -v
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .

cd ..
git diff --check
git status --short
```

Expected: all tests/lint/format pass; only assigned implementation, tests, lockfile와 engineering docs differ from design commit.

- [ ] **Step 6: Task 5 커밋**

```sh
git add \
  backend/apps/narrative_memory/composition.py \
  backend/tests/narrative_memory/test_agent_composition.py \
  backend/docs/llm-audit-logging.md \
  backend/docs/backend-coding-rules.md \
  backend/README.md \
  llm-agent/src/narrative_analysis_agent/AGENTS.md \
  llm-agent/src/dialogue_generation_agent/AGENTS.md \
  llm-agent/docs/llm-agent-coding-rules.md \
  llm-agent/docs/dialogue-generation-agent-coding-rules.md
git commit -m "문서: LLM 감사 로깅 운영 경계 동기화"
```

---

### Task 6: Read-only review, remediation과 최종 검증

**Files:**
- Review boundary: all files changed since `3f3a8e2`
- Modify only if accepted review findings require a repair in their owning paths

**Interfaces:**
- Consumes: approved design, Tasks 1-5 handoffs and verification evidence
- Produces: backend-review native conclusion, normalized verdict, finding dispositions, clean final verification

- [ ] **Step 1: implementation diff 자체 검토**

Run:

```sh
git diff --stat 3f3a8e2..HEAD
git diff --check 3f3a8e2..HEAD
git diff 3f3a8e2..HEAD -- \
  llm-agent/src/llm_agent_audit \
  llm-agent/src/narrative_analysis_agent/agent.py \
  llm-agent/src/dialogue_generation_agent/agent.py \
  backend/infrastructure/audit \
  backend/apps/narrative_memory/composition.py
```

Confirm exact prompt files have no diff, `docs/domains/*`, frontend and OpenAPI have no diff, and all model calls pass through the common decorator.

- [ ] **Step 2: read-only backend-review dispatch**

Assign the complete Python boundary to `backend-review` with:

- base `3f3a8e2`, exact HEAD
- affected entry points `NarrativeAnalysisAgent.analyze_scene`, `DialogueGenerationAgent.generate_dialogue`, `AuditedAgentRunner.run`, `JsonlAgentAuditSink.append`, backend composition builders
- approved design path and all acceptance criteria
- no OpenAPI baseline because no consumer-facing operation changes
- implementation handoff, test commands/results and explicit read-only ownership
- review requirements: architecture, fail-closed semantics, cancellation, prompt/output compatibility, JSONL isolation, permissions, encryption/AAD, retention, credential/telemetry leakage, deterministic tests and docs

Record native conclusion and normalize `No blocking findings` to `review-complete`; `Changes required` or `Blocked` to `changes-required`.

- [ ] **Step 3: findings triage와 remediation**

For every finding record `accept`, `reject` with repository evidence, or genuine decision escalation. Resolve every accepted finding. Send backend-owned repairs to the backend implementer when practical; keep llm-agent common/agent repairs in the main thread. Re-run the focused checks for every repair. Re-dispatch the same reviewer for Blocking/High or any behavior-material repair with original finding IDs and exact fix diff.

- [ ] **Step 4: verification-before-completion 실행**

Invoke `superpowers:verification-before-completion`, then run fresh:

```sh
cd llm-agent
mise exec -- uv run pytest -m "not live"
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .

cd ../backend
mise exec -- uv run pytest
mise exec -- uv run ruff check .
mise exec -- uv run ruff format --check .

cd ..
git diff --check
git status --short --branch
```

Expected: all commands exit 0, no unexpected untracked/generated files, review gate clear, accepted findings resolved.

- [ ] **Step 5: final integration commit if remediation changed files**

Only when uncommitted accepted-finding repairs exist:

```sh
git diff --name-only
# 위 목록에서 disposition에 기록된 accepted-finding 수정 파일만 각각 git add -- PATH로 stage한다.
git commit -m "수정: LLM 감사 로깅 리뷰 결과 반영"
```

Do not create an empty commit.

- [ ] **Step 6: completion handoff**

Report implemented behavior, changed paths, design/plan commits, no API/UI/domain impact, backend-review native conclusion/normalized verdict, every finding disposition, exact verification results, accepted deviations and remaining risks. Confirm ticket 11 only after all gates pass and print the required completion marker as the final line.
