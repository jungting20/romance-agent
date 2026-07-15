# 도메인 계약

이 디렉터리는 Muse 로맨스 집필 시스템의 기술 중립적인 비즈니스 계약을 설명한다. 프런트엔드와 백엔드는 같은 용어와 경계를 사용하며, 구현 세부 사항보다 이 문서에 정의된 소유권과 불변 조건을 우선한다.

## 컨텍스트 맵

```text
Projects
   └─ Story Design
        ├─ Story Bible
        └─ Manuscript ─┬─ Narrative Memory
                       └─ Writing Assistant

Story Bible ──────────────┐
Narrative Memory ───────├─ Writing Assistant 일관성 검사
Manuscript ───────────────┘
```

화살표는 작업 흐름에서 정보가 전달되는 방향을 나타내며 다른 도메인의 상태를 직접 변경할 수 있다는 뜻이 아니다. 여러 도메인이 필요한 작업은 애플리케이션 유스케이스가 조정한다.

## 도메인 목록

| 도메인            | 소유하는 책임                   | 계약 문서                                      |
| ----------------- | ------------------------------- | ---------------------------------------------- |
| Projects          | 프로젝트 식별과 목록 메타데이터 | [projects.md](./projects.md)                   |
| Story Design      | 트로프와 초기 이야기 콘셉트     | [story-design.md](./story-design.md)           |
| Story Bible       | 인물과 세계관의 기준 정보       | [story-bible.md](./story-bible.md)             |
| Manuscript        | 장면과 원고 텍스트              | [manuscript.md](./manuscript.md)               |
| Narrative Memory  | 재생성 가능한 분석과 JSON 스냅샷 | [narrative-memory.md](./narrative-memory.md)    |
| Writing Assistant | 명시적 집필 요청과 제안         | [writing-assistant.md](./writing-assistant.md) |

## 도메인 간 유스케이스

### 프로젝트 작업공간 생성

1. Story Design이 트로프와 두 주인공을 포함한 콘셉트를 검증한다.
2. Projects가 프로젝트 메타데이터를 만든다.
3. Story Bible이 두 주인공과 초기 세계관 정보를 만든다.
4. Manuscript가 프로젝트에 속한 첫 장면을 만든다.

### 집필 제안 적용

1. 애플리케이션 유스케이스가 현재 장면 문맥을 Writing Assistant에 전달한다.
2. Writing Assistant가 삽입, 교체, 진단 중 하나의 제안을 반환한다.
3. 사용자가 적용을 요청한 삽입 또는 교체 제안만 Manuscript에 전달한다.
4. Manuscript가 커서 또는 선택 범위를 검증하고 원고를 변경한다.

### Narrative Memory 장면 재분석

1. 명시적 애플리케이션 유스케이스가 Manuscript의 장면 리비전과 본문을 Narrative Memory에 전달한다.
2. Narrative Memory가 해당 장면의 `pending` 후보를 대체하고 장면 요약, 근거, 관계 사건과 장소 사건
   후보, 새 스냅샷을 반환한다.
3. 기존 확인 사실의 근거가 사라진 경우, 애플리케이션 유스케이스가 Story Bible에 `needs_review`
   전환을 요청한다.
4. Narrative Memory는 Manuscript나 Story Bible을 직접 변경하지 않는다.

### 명시적 일관성 검사

1. 사용자가 일관성 검사를 명시적으로 요청한다.
2. 애플리케이션 유스케이스가 Manuscript의 요청 장면, Story Bible의 확인된 관계 사건과 장소 사건,
   Narrative Memory의 제한된 장면 요약을 Writing Assistant에 전달한다.
3. Writing Assistant가 진단 제안을 반환하며, 확인된 사실을 근거로 삼은 진단은 Story Bible 확인 사실
   식별자를 인용한다.
4. 미해결 또는 `needs_review` 후보는 확정 사실로 전달되지 않는다.

## 의존 규칙

- 도메인은 다른 도메인의 상태를 직접 변경해서는 안 된다.
- 원고 텍스트는 Manuscript만 소유하고 변경해야 한다.
- Writing Assistant는 요청받기 전에 원고 문맥을 읽거나 제안을 생성해서는 안 된다.
- Narrative Memory는 Manuscript에서 파생된 재생성 가능한 기억을 소유하며 Manuscript를 직접 변경하지 않는다.
- Narrative Memory 후보는 자동 승인되지 않으며 `needs_review` 후보는 Story Bible 사실이 아니다.
- Writing Assistant는 명시적 일관성 검사에서만 제한된 Narrative Memory 요약을 읽을 수 있다.
- 여러 도메인을 조합하는 흐름은 애플리케이션 유스케이스가 담당해야 한다.
- 이 문서들은 화면, 저장소, API, 프레임워크와 무관한 계약이어야 한다.
