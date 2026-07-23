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

Story Bible ──────────────┐
Manuscript ───────────────┼─ Writing Assistant 대화 장면 생성
호출자가 선택한 이전 기억 ─┘
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
2. Narrative Memory의 agent가 현재 v2 프로젝트 그래프를 읽기 전용으로 한 번 조회하고,
   같은 snapshot을 모든 청크에 제공해 순서가 보존된 exact 청크 그래프를 반환한다.
3. backend가 청크 로컬 ID를 프로젝트 ID로 재매핑하고 해당 장면 그래프를 교체한 뒤,
   현재 장면 레코드 전체에서 버전이 있는 프로젝트 snapshot을 재구성해 원자적으로 저장한다.
4. agent가 읽은 source snapshot version과 저장 직전의 current version이 다르면 장면과
   프로젝트 snapshot을 덮어쓰지 않고 동시성 충돌로 거부한다.
5. Narrative Memory는 Manuscript나 Story Bible을 직접 변경하지 않는다.

### 명시적 일관성 검사

1. 사용자가 일관성 검사를 명시적으로 요청한다.
2. 애플리케이션 유스케이스가 Manuscript의 요청 장면, Story Bible의 확인된 관계 사건과 장소 사건,
   Narrative Memory의 제한된 장면 요약을 Writing Assistant에 전달한다.
3. Writing Assistant가 진단 제안을 반환하며, 확인된 사실을 근거로 삼은 진단은 Story Bible 확인 사실
   식별자를 인용한다.
4. Narrative Memory의 미해결 참조나 모순과 Story Bible의 `needs_review`
   사실은 확정 사실로 전달되지 않는다.

### 대화 장면 생성

1. 사용자가 대화 장면 생성을 명시적으로 요청한다.
2. 애플리케이션 유스케이스가 Story Bible에서 선택한 세계관과 인물 설정, Manuscript의 원본 장면 ID와
   현재 문맥, 호출자가 선택한 비권위 이전 기억, 장면 목적과 인물별 정보 경계를 Writing Assistant에
   전달한다.
3. Writing Assistant가 한 생성 시도를 고유 generation ID로 식별하고, 대화 발화와 정보 흐름을 포함한
   strict JSON 결과를 반환한다.
4. 현재 공개 금지 정보가 실제 대사에 노출되거나 metadata가 누출을 보고하면 전체 결과를 거부한다.
5. 생성 결과는 Manuscript를 직접 변경하지 않으며 적용은 별도 애플리케이션 유스케이스가 조정한다.

## 의존 규칙

- 도메인은 다른 도메인의 상태를 직접 변경해서는 안 된다.
- 원고 텍스트는 Manuscript만 소유하고 변경해야 한다.
- Writing Assistant는 요청받기 전에 원고 문맥을 읽거나 제안을 생성해서는 안 된다.
- Narrative Memory는 Manuscript에서 파생된 재생성 가능한 기억을 소유하며 Manuscript를 직접 변경하지 않는다.
- Narrative Memory 지식 그래프는 Story Bible 사실로 자동 전환되지 않으며,
  미해결 참조와 모순은 확정 사실이 아니다.
- Writing Assistant는 명시적 일관성 검사에서만 제한된 Narrative Memory 요약을 읽을 수 있다.
- Writing Assistant 대화 장면 생성의 관련 이전 기억은 호출자가 선택한 비권위 문맥이며 Narrative
  Memory 확정 사실이나 Story Bible 기준 정보로 자동 승격되지 않는다.
- 여러 도메인을 조합하는 흐름은 애플리케이션 유스케이스가 담당해야 한다.
- 이 문서들은 화면, 저장소, API, 프레임워크와 무관한 계약이어야 한다.
