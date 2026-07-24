# LLM 감사 로깅 운영 경계

LLM 감사 로그의 구체 저장소는 backend 애플리케이션이 소유한다. `llm_agent_audit`는
공통 `AgentAuditSink` 포트와 `AuditedAgentRunner` decorator만 제공하고 파일, 키,
로거 또는 provider 자격 증명을 소유하지 않는다. 실행 애플리케이션은 sink를 만들고
`build_narrative_analysis_agent()` 또는 `build_analyze_scene_use_case()`의 선택적
`audit_sink`에 주입한다. builder는 sink를 만들거나 바꾸지 않고 동일 객체를 public
agent facade에 전달한다.

## 기본 저장 정책

`JsonlAgentAuditSink`는 애플리케이션이 지정한 private directory에 두 독립 JSONL
stream을 둔다.

- `llm-audit-metadata.jsonl`은 기본으로 기록되는 sanitized metadata stream이다.
- `llm-audit-sensitive.jsonl`은 raw capture가 명시적으로 활성화되고 sensitive payload가
  있을 때만 AES-256-GCM envelope을 기록한다.
- directory mode는 `0700`, 각 log file mode는 `0600`이다.
- `capture_sensitive_content`의 기본값은 `False`다. 따라서 기본 구성은 raw prompt,
  raw response, validated output을 쓰지 않으며 sensitive file도 만들지 않는다.
- 두 stream은 midnight rotation으로 회전한다. 기본 보존 기간은 metadata 30일,
  sensitive 7일이다.
- 전용 logger는 `propagate = False`다. handler를 root 또는 다른 일반 logger에
  붙이지 않으므로 감사 event가 일반 application log로 전파되지 않는다.

metadata에는 schema, event/run/attempt ID, sanitized model configuration, prompt
identity hash, 시간, 상태, usage, sanitized error만 기록한다. provider credential과
허용 목록 밖의 model setting은 기록하지 않는다. 감사 log와 일반 log 어느 쪽에도
prompt 본문, provider response, encryption key 또는 credential을 기록하지 않는다.

## 구성

기본 raw-off 구성은 다음처럼 application startup/composition code가 만든다.

```python
from infrastructure.audit import AgentAuditLogConfig, JsonlAgentAuditSink
from narrative_analysis_agent import packaged_prompt_path

from apps.narrative_memory.composition import build_analyze_scene_use_case

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

Raw capture는 기본 동작을 바꾸는 별도 운영 결정이다. 실행 애플리케이션이 이미
획득한 정확히 32-byte AES key와 non-secret key ID를 직접 주입할 때만 활성화한다.
키를 환경 변수 이름, 문자열 리터럴 또는 log에 넣지 않는다.

```python
audit_sink = JsonlAgentAuditSink(
    AgentAuditLogConfig(
        directory=data_root / "private" / "llm-audit",
        capture_sensitive_content=True,
        encryption_key=already_obtained_32_byte_key,
        encryption_key_id=non_secret_key_id,
    )
)
```

구성 오류, directory/file I/O 또는 required audit append가 실패하면
`AuditedAgentRunner`는 `AgentAuditWriteError`를 내고 성공 결과를 반환하지 않는다
(fail-closed). 이미 발생한 provider/validation failure와 cancellation의 terminal audit
append는 원래 failure/cancellation을 가리지 않도록 best effort다.
