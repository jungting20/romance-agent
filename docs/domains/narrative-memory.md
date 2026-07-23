# Narrative Memory 도메인 계약

## 목적과 책임

Narrative Memory는 Manuscript 장면에서 다시 만들 수 있는 청크별 지식 그래프
분석 결과와 명시적 인물 기억, 장면별 그래프 출처, 버전이 있는 프로젝트
지식 그래프 snapshot을
소유한다. 추출 결과를 작품의 확정 사실로 취급하지 않으며 Manuscript나 Story Bible을
직접 변경하지 않는다.

`llm-agent`는 프로젝트 그래프를 읽기 전용으로 조회하고 정확한 청크별 분석 결과를
반환한다. backend는 청크 로컬 ID를 프로젝트 ID로 재매핑하고, 장면과 프로젝트
그래프를 병합·재구성하며, snapshot을 기록하는 유일한 write owner다.

## 보편 언어

- **장면 분석 리비전:** 특정 Manuscript 장면 본문 버전에 대해 수행한 분석의 버전
- **청크 분석:** 불변 장면 본문의 유한한 부분과 그 부분의 exact
  `KnowledgeGraphOutput`을 묶은 결과
- **지식 그래프 출력:** 문서 요약과 인물·장소·사건·관계·이동·공통 참조·
  미해결 참조·모순·인물 기억을 공개 strict schema로 표현한 청크 단위 해석
- **인물 기억:** 현재 청크가 특정 인물이 기억·망각·억압·불확실한 기억 또는
  거짓 기억을 가진다고 명시한 경우만 생성하는 독립적이고 비권위적인 파생 항목
- **기억 주체:** 해당 기억 상태를 가진 인물. `character_id`는 올바른 인물 ID만
  참조한다.
- **기억 대상:** 종류·참조 ID·설명을 묶은 구조화된 `MemoryTarget`.
  `character`·`location`·`event`·`relation`은 선언한 종류의 ID를 반드시 연결하고,
  `described_event`·`described_relation`·`other`는 ID 없이 명시적인 기억 대상을
  설명한다. 불명확한 대상을 설명 전용 대상으로 우회하지 않는다.
- **기억 상태:** `remembered`는 기억함, `forgotten`은 잊었음, `repressed`는 억압함,
  `uncertain`은 기억 여부가 불확실함, `false_memory`는 거짓 기억임을 표현한다.
  일반 믿음·지각이나 Story Bible 검토 상태를 표현하지 않는다.
- **일반 추출 항목:** confidence가 유한한 `0.8..1.0` 범위인 인물, 장소, 사건,
  관계, 이동 또는 공통 참조
- **미해결 참조:** 대상이 확정되지 않거나 confidence가 `0.8`보다 낮아 일반
  추출 항목으로 다룰 수 없는 표현과 가능한 대상
- **근거:** 비어 있지 않고 청크 원문에 실제로 포함된 `evidence` 또는
  `first_mention` 문자열.
  장면 절대 offset이나 별도의 영속 evidence 객체를 생성하지 않는다.
- **장면 그래프 레코드:** 프로젝트·장면 식별자, 장면 리비전·순서와 미해결
  참조·모순을 포함한 병합 `KnowledgeGraphOutput`을 보관하며, 해당 장면
  출처의 권위 있는 소유자인 backend 저장 단위
- **프로젝트 지식 그래프 snapshot:** 현재 장면 그래프 레코드의 값을 평탄한
  모음으로 집계한 버전 있는 불변 v2 JSON 구조. 평탄한 항목에 새
  `scene_id`나 provenance 필드를 추가하지 않는다.
- **source snapshot version:** agent가 분석 시작 시 읽은 프로젝트 snapshot 버전이며,
  backend 저장의 낙관적 동시성 기대값. current record가 없을 때는 저장되지
  않은 개념적 empty snapshot의 버전 `0`을 사용한다.

v1의 `ChunkExtraction`, 추출 후보와 `pending`/`approved`/`rejected`/`needs_review`
상태, 장면 절대 evidence offset, 장면·프로젝트 관계 snapshot은 v2 보편 언어가
아니며 호환되지 않는다.

## 핵심 모델

- `KnowledgeGraphOutput`은 하나의 `Document`, `Entities` 안의 인물·장소·사건,
  관계, 이동, 공통 참조, 미해결 참조, 모순, 인물 기억을 각각 불변 튜플로
  가진다. `character_memories`는 `Entities`나 관계의 속성이 아닌 독립 모음이다.
- `CharacterMemory`는 기억 ID, 주체 인물 ID, 구조화된 대상, 기억 내용·상태,
  선택적 시간 표현, 장면 순서, 현재 청크의 근거와 confidence를 가진다.
- `AnalyzedChunk`는 청크 식별자, 0부터 시작하는 연속 순번, 장면 기준
  시작·끝 위치, 불변 원문과 exact `KnowledgeGraphOutput`을 묶는다.
- `SceneAnalysis`는 프로젝트·장면 식별 정보, 장면 리비전·순서, source snapshot
  version과 입력 순서가 보존된 `AnalyzedChunk` 튜플을 가진다.
- `SceneGraphRecord`는 하나의 장면 리비전과 순서에 대한 인물 기억·미해결 참조·모순을
  포함한 병합 그래프를 해당 프로젝트·장면 출처와 함께 보관한다.
- `ProjectKnowledgeGraphSnapshot`은 project ID, 0 이상의 snapshot version, v2 schema
  version, 장면별 `Document`, 현재 장면 레코드에서 통합·집계한 인물·장소·
  사건·관계·인물 기억·이동·공통 참조·미해결 참조·모순의 평탄한 모음을 가진다.

## 불변 조건

### 장면 분석

- 명시적 장면 분석의 호출자는 Manuscript가 제공한 project ID, scene ID, 장면
  리비전·순서, 불변 본문만 요청에 담는다. Narrative Memory는 이 입력을 얻기 위해
  다른 도메인을 조회하지 않는다.
- `llm-agent`는 분석 시작 시 구성된 Narrative Memory DB에서 해당 project ID의 current
  v2 snapshot을 정확히 한 번 읽고 분석 종료 전에 읽기 전용 연결을 닫아야 한다.
  backend는 그 DB와 필수 테이블을 먼저 초기화하고 동일한 경로를 agent에 전달한다.
- 하나의 분석 실행은 시작 시 읽은 하나의 project snapshot을 모든 청크에 동일하게
  제공해야 하며 앞선 청크 출력을 뒤 청크 입력에 누적하지 않는다.
- 장면 본문은 최대 300자, 50자 중첩 청크로 나누고 숫자 순서대로 직렬 처리한다.
  각 청크는 모델에 정확히 한 번만 전달하며 재시도하지 않는다.
- 어느 청크든 실패하면 뒤 청크를 호출하지 않고, 앞선 청크의 부분 결과도
  반환·병합·저장하지 않는다.
- 청크 식별자는 scene ID, 장면 리비전, 0부터 시작하는 연속 순번을 정확히
  인코딩한다. 순번 `n`의 시작 위치는 `n * 250`이고 청크 너비는 `1..300`이다.
  마지막 청크를 제외한 모든 청크의 너비는 300이며, 인접 청크의 50자 중첩 원문은
  정확히 같아야 한다. 여러 청크가 있으면 마지막 청크는 중첩 범위 넘어의 문자를
  하나 이상 포함해야 한다.
- 성공한 분석은 exact `KnowledgeGraphOutput`을 담은 `AnalyzedChunk`를 숫자 순서대로
  보존한 튜플로 반환한다. 청크 결과를 별도의 후보나 장면 snapshot으로
  변환하지 않는다.

### 지식 그래프 출력

- 모든 공개 모델은 추가 필드를 거부하는 strict 불변 모델이고 모음은 튜플이어야
  한다.
- `document.chapter_id`는 요청의 scene ID와 정확히 같아야 한다. 열거형 값은 공개
  schema의 허용 값만 사용하고 event·relation·movement type의 확장 값은
  `UPPER_SNAKE_CASE`를 만족해야 한다.
- 인물·장소·사건·관계·이동·공통 참조의 confidence는 모두 유한하고 `0.8..1.0`
  닫힌 구간에 있어야 한다. 대상이 확정되지 않거나 `0.8` 미만인 항목은
  일반 항목에 두지 않고 `unresolved_references`로 분리한다.
- 인물 기억은 인물이 기억·망각·억압·불확실한 기억·거짓 기억 중 하나를
  가진다고 현재 청크가 명시한 경우만 추출한다. 사실이나 사건 참여, 지식,
  믿음·지각, flashback에 등장함, 회상 장면이나 회고적 서술만으로는 특정
  인물의 기억을 추론하지 않는다.
- 기억 주체나 대상이 모호하거나, 대상의 종류를 안전하게 결정할 수 없거나,
  confidence가 `0.8` 미만이면 일반 인물 기억을 만들지 않고
  `unresolved_references`로 분리한다.
- 청크 로컬 기억 ID는 중복되지 않아야 하며, 기억 주체는 해당 청크 출력 또는
  읽은 프로젝트 그래프의 인물을 참조해야 한다. 연결형 대상은 선언한 종류의
  로컬 또는 기존 프로젝트 ID만 참조하고, 설명 전용 대상은 ID를 참조하지 않는다.
  `false_memory`의 검증되지 않은 명제는 세계의 사건이나 관계를 생성하지 않고
  설명 전용 대상으로 보존한다.
- 모든 인물 기억은 요청의 장면 순서와 정확히 같은
  `scene_sequence`, 현재 청크에 그대로 포함된 비어 있지 않은 근거,
  유한한 `0.8..1.0` confidence를 가져야 한다. 이미 저장된 프로젝트 그래프는
  문맥일 뿐 현재 청크의 근거로 전환되지 않는다.
- 청크 로컬 character·location·event·relation ID는 종류별로 유일해야 한다.
  location parent, event participant·location, relation 양끝과 사건 anchor, movement,
  coreference, unresolved reference, contradiction은 같은 청크 출력 또는 읽은 프로젝트
  그래프에 존재하는 올바른 종류의 ID만 참조해야 한다.
- 모든 `evidence`와 `first_mention`은 비어 있지 않고 해당 청크의 불변
  원문에 그대로 포함되어야 한다.
- `llm-agent`는 청크 로컬 ID를 durable ID로 해석하거나 새 영속 ID를 생성하지
  않는다. 청크 간 재매핑·병합·중복 제거도 수행하지 않는다.

### 장면 병합과 프로젝트 snapshot

- backend는 인물을 기존 프로젝트 인물과 명시적 별칭 연결이 있을 때만
  기존 ID로 재사용하며 canonical name이 같다는 사실만으로는 재사용하지
  않는다. 장소는 canonical name 또는 별칭이 일치하는 기존 장소가 유일할
  때는 기존 ID를 재사용하고 여러 기존 장소와 일치하면 별도 대상으로 유지한다.
  여러 청크의 명확히 같은 신규 대상은 하나로 통합하고, 애매한 대상은
  별도로 유지하며 `POSSIBLE_SAME_AS` 관계를 보존한다. 신규 ID는
  `chunk.start_offset + chunk.text.find(first_mention)` 또는
  `chunk.start_offset + chunk.text.find(evidence)`로 구한 장면 절대 최초 등장
  위치, 정규화 이름과 결정적 tie breaker로
  할당한다.
- backend는 인물·장소·사건·관계 ID의 프로젝트 전역 유일성을 보장하고 관계,
  이동, 공통 참조, 미해결 참조와 모순의 모든 로컬 참조를 보존된
  프로젝트 ID로 재매핑한다. parent·participant·location·event 참조도 해당
  종류의 ID만 가리켜야 한다.
- backend는 기억 주체를 인물 ID map으로, 연결된 기억 대상을 선언한
  인물·장소·사건·관계의 typed ID map으로 프로젝트 ID에 재매핑한다.
  기존 프로젝트 대상을 참조하는 기억은 그 대상과 관계의 필수 의존 항목을
  장면 그래프에 포함해 참조 무결성을 지키지만, 이를 새 근거나 권위 승격으로
  취급하지 않는다.
- backend는 현재 청크 근거를 다시 확인하고, 연결된 ID를 제외한 기억의 내용·
  상태·시간 표현·장면 순서·근거·confidence를 그대로 보존한다. 중첩 청크에서
  절대 근거 위치와 주체·대상·내용·상태·시간·장면 순서·confidence가 결정적으로
  같은 명시적 기억만 하나로 합치며, 의미가 다른 기억은 별도로 보존한다.
  새 기억 ID는 기존 최대값 다음부터 결정적으로 할당하고, 다른 장면의 내용이
  같다는 이유만으로 같은 기억 ID를 공유하지 않는다.
- 동일 이름만으로 다른 인물을 자동 병합하지 않는다. 관계 변화는 기존 관계를
  덮어쓰지 않고 종료 상태와 새 관계 기록을 함께 유지한다.
- 재분석은 해당 project ID와 scene ID의 장면 그래프 레코드를 새 리비전·순서·
  그래프로 교체한다. 교체된 장면의 이전 기억은 제거하고 다른 현재 장면의
  기억은 보존한다. 프로젝트 snapshot은 현재 장면 레코드 전체를
  `(scene_sequence, scene_id)` 순서로 집계해 매번 재구성하므로 삭제되거나 교체된
  장면의 이전 항목이 남지 않는다.
- repository에 저장된 각 `SceneGraphRecord`가 자신의 인물 기억·미해결 참조·
  모순을 포함한
  장면 출처의 권위 있는 소유자다. 출처는 레코드의 project ID, scene ID,
  리비전과 순서로 추적한다.
- 프로젝트 snapshot은 현재 장면 레코드의 값을 장면 순서대로 집계한
  `documents`, character memories, unresolved references와 contradictions를 포함하지만,
  각 평탄한
  항목에 새 scene ID나 provenance 필드를 추가하지 않는다. backend는 저장된
  장면 레코드를 통해 평탄한 값의 장면 출처를 추적할 수 있다.
- current record가 없을 때 reader가 생성하는 개념적 빈
  `ProjectKnowledgeGraphSnapshot`은 schema `project-knowledge-graph-snapshot-v2`, snapshot
  version `0`과 빈 모음을 가지며 repository에 저장하지 않는다. 첫 장면/프로젝트
  snapshot은 version `1`로 원자적 저장하고 이후 저장은 current version을
  1씩 증가시킨다. JSON codec은 v2만 canonical UTF-8 JSON으로 인코딩·디코딩하고
  v1, 알 수 없는 version, 추가 필드와 의미 불변 조건 위반을 거부한다.
- 저장된 프로젝트 snapshot은 1 이상의 version과 장면 `chapter_id`의 유일성, 전역 graph
  ID 유일성, 모든 parent·relation·movement·coreference 및 기타 타입 참조의
  존재와 올바른 종류, confidence 불변 조건을 인코딩·디코딩·저장 경계에서
  동일하게 검증해야 한다.
- 장면과 프로젝트 그래프의 기억 ID는 전역으로 유일해야 하고, 주체는 인물만,
  연결형 대상은 선언한 정확한 종류만 참조해야 한다. 잘못된 종류나 끊어진
  기억 참조, 설명 전용 대상의 ID, 빈 내용·설명·근거, 잘못된 상태·장면
  순서·confidence를 모델·병합·codec·repository·read 경계에서 거부한다.
- `character_memories`는 기존 v2 호환성을 깨지 않는 추가 확장이다. 이 필드가 없는
  기존 v2 장면·프로젝트 payload는 빈 튜플로 읽고, 새로 인코딩하는 canonical v2
  JSON은 비어 있거나 채워진 `character_memories`를 항상 출력한다. 읽기는 기존
  current·이력 payload의 불변 bytes와 hash를 재작성·재해시하지 않는다. schema ID와
  SQLite table·transaction은 유지하며 v1 decoder, v3 전환, 자동 migration·DB 삭제를
  도입하지 않는다.
- backend는 저장 직전 current snapshot version을 다시 읽고 agent가 반환한 source
  snapshot version과 정확히 같을 때만 장면 레코드와 새 프로젝트 snapshot을
  한 transaction으로 기록한다. 낮거나 높은 version mismatch는 모두 동시성 충돌로
  거부하고 current snapshot을 덮어쓰지 않는다.
- agent는 프로젝트 DB를 쓰거나 schema를 생성·변경·복구하지 않는다. backend만
  v2 schema 초기화, 장면 교체, 프로젝트 병합과 저장 transaction을 수행한다.

## 유스케이스

### 장면 분석

호출자가 Manuscript에서 전달한 특정 장면 리비전의 불변 본문과 식별·순서 정보를
명시적으로 입력한다. agent는 current project graph를 읽기 전용으로 한 번 읽고,
본문을 300자/50자 중첩 청크로 나누어 숫자 순서대로 각각 한 번 분석한다.
성공하면 source snapshot version과 exact 청크별 `KnowledgeGraphOutput` 튜플을 반환하고,
어느 청크든 실패하면 부분 결과를 반환하지 않는다.
인물 기억은 현재 청크의 명시적 기억 표현만 독립 `character_memories`로 추출하며,
사실·믿음·지각·flashback 서술로부터 임의로 추론하지 않는다. 모호하거나 낮은
confidence의 주체·대상은 일반 기억 대신 미해결 참조로 남긴다.

### 장면 병합과 프로젝트 snapshot 저장

backend는 성공한 분석의 청크 로컬 ID를 프로젝트 ID로 재매핑하고 장면 결과를
하나의 `SceneGraphRecord`로 병합한다. 해당 장면 레코드를 교체한 뒤 현재
장면 레코드 전체에서 다음 버전의 `ProjectKnowledgeGraphSnapshot`을 재구성한다.
인물 기억의 주체와 연결 대상을 typed ID map으로 재매핑하고, 중첩 청크의
결정적으로 같은 기억만 병합하며, 근거·장면 순서와 나머지 의미 필드를 보존한다.
source snapshot version과 current version이 같을 때만 장면과 project snapshot을 원자적으로
저장한다. current가 없는 첫 시도는 source version `0`과 비교하되 첫 저장
version은 `1`이므로, 같은 개념적 version `0`을 사용한 다른 분석은 첫 저장 후
stale로 거부된다. 분석·병합·저장 실패 시 부분 상태를 게시하지 않는다.

### 프로젝트 그래프 조회

agent는 분석 문맥으로 사용할 current v2 snapshot만 읽기 전용으로 조회한다. project
record가 없으면 version 0의 빈 graph를 사용하지만, DB 접근 실패, 손상된 JSON,
v1 또는 알 수 없는 schema는 provider 호출 전에 분석 실패로 거부한다.

## 입력과 출력

- Manuscript의 project ID, scene ID, 장면 순서·리비전과 불변 본문을 명시적
  애플리케이션 유스케이스를 통해 입력받는다.
- 성공한 장면 분석은 source snapshot version과 exact 지식 그래프 출력이 포함된
  순서 보존 청크 튜플을 반환한다.
- backend 저장 워크플로는 장면 출처 레코드와 version이 있는 canonical v2 프로젝트
  지식 그래프 JSON snapshot을 반환한다.
- 각 `KnowledgeGraphOutput`, `SceneGraphRecord`, `ProjectKnowledgeGraphSnapshot`은 기타 그래프
  항목과 분리된 인물 기억 모음을 가질 수 있다.
- Writing Assistant의 명시적 일관성 검사 유스케이스에 필요한 범위로 제한한 장면
  문서 요약과 지식 그래프를 제공할 수 있다. 인물 기억은 자동으로 Writing Assistant에
  전달하지 않고, 호출자가 명시적으로 선택한 이전 기억만 비권위적 문맥으로 제공한다.

## 책임지지 않는 영역

- Manuscript 장면, 장면 순서, 장면 리비전, 원고 본문의 소유와 변경
- Story Bible 사실의 직접 생성, 변경, 삭제 또는 추출 결과의 자동 사실 전환
- 인물 기억의 내용·`false_memory`를 확정 사실이나 Story Bible 검토 상태로 승격
- 저장된 인물 기억을 Writing Assistant의 이전 기억 입력으로 자동 선택
- Writing Assistant 제안 또는 일관성 진단 생성
- HTTP API, OpenAPI, frontend, 백그라운드 큐
- 저장소·데이터베이스·외부 모델 provider 제품의 선택
- `llm-agent`의 프로젝트 graph 쓰기, durable ID 할당, 청크 간 병합 또는 중복 제거
