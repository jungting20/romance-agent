# 도메인 계약 문서화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 현재 코드에 존재하는 5개 바운디드 컨텍스트의 목적, 언어, 모델, 불변 조건, 유스케이스, 입출력, 비책임 영역을 한글 계약 문서로 작성한다.

**Architecture:** `docs/domains/README.md`가 기술 중립적인 컨텍스트 맵과 문서 인덱스를 제공한다. 각 도메인은 하나의 독립 문서로 관리하며, 프런트엔드와 향후 Python 백엔드는 이 문서를 공통 비즈니스 계약으로 사용한다.

**Tech Stack:** Markdown, 도메인 주도 설계, 현재 TypeScript 도메인 모델과 Vitest 테스트.

## Global Constraints

- 파일명과 코드 식별자는 영문을 유지하고 제목과 설명 본문은 한글로 작성한다.
- 코드에 이미 존재하는 `Projects`, `Story Design`, `Story Bible`, `Manuscript`, `Writing Assistant` 이름을 그대로 사용한다.
- 불변 조건은 검증 가능한 문장으로 작성한다.
- TypeScript 인터페이스를 줄 단위로 복제하지 않는다.
- React, localStorage, Vite, Python 프레임워크, 데이터베이스, 전송 방식에 의존하지 않는다.
- 승인되거나 구현되지 않은 제품 확장 사항을 현재 계약에 포함하지 않는다.

---

### Task 1: 도메인 인덱스와 컨텍스트 맵 작성

**Files:**

- Create: `docs/domains/README.md`

**Interfaces:**

- Consumes: `docs/superpowers/specs/2026-07-13-domain-contract-documentation-design.md`의 문서 구조와 컨텍스트 맵.
- Produces: 모든 도메인 계약 문서의 진입점과 도메인 간 의존 규칙.

- [ ] **Step 1: 도메인 문서 디렉터리와 인덱스 작성**

`docs/domains/README.md`를 다음 내용으로 작성한다.

````markdown
# 도메인 계약

이 디렉터리는 Muse 로맨스 집필 시스템의 기술 중립적인 비즈니스 계약을 설명한다. 프런트엔드와 백엔드는 같은 용어와 경계를 사용하며, 구현 세부 사항보다 이 문서에 정의된 소유권과 불변 조건을 우선한다.

## 컨텍스트 맵

```text
Projects
   └─ Story Design
        ├─ Story Bible
        └─ Manuscript ── Writing Assistant
```

화살표는 작업 흐름에서 정보가 전달되는 방향을 나타내며 다른 도메인의 상태를 직접 변경할 수 있다는 뜻이 아니다. 여러 도메인이 필요한 작업은 애플리케이션 유스케이스가 조정한다.

## 도메인 목록

| 도메인            | 소유하는 책임                   | 계약 문서                                      |
| ----------------- | ------------------------------- | ---------------------------------------------- |
| Projects          | 프로젝트 식별과 목록 메타데이터 | [projects.md](./projects.md)                   |
| Story Design      | 트로프와 초기 이야기 콘셉트     | [story-design.md](./story-design.md)           |
| Story Bible       | 인물과 세계관의 기준 정보       | [story-bible.md](./story-bible.md)             |
| Manuscript        | 장면과 원고 텍스트              | [manuscript.md](./manuscript.md)               |
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

## 의존 규칙

- 도메인은 다른 도메인의 상태를 직접 변경해서는 안 된다.
- 원고 텍스트는 Manuscript만 소유하고 변경해야 한다.
- Writing Assistant는 요청받기 전에 원고 문맥을 읽거나 제안을 생성해서는 안 된다.
- 여러 도메인을 조합하는 흐름은 애플리케이션 유스케이스가 담당해야 한다.
- 이 문서들은 화면, 저장소, API, 프레임워크와 무관한 계약이어야 한다.
````

- [ ] **Step 2: 링크와 한글 본문 확인**

Run:

```sh
rg -n "projects.md|story-design.md|story-bible.md|manuscript.md|writing-assistant.md" docs/domains/README.md
```

Expected: 다섯 계약 문서 링크가 모두 출력된다.

- [ ] **Step 3: 인덱스 커밋**

```sh
git add docs/domains/README.md
git commit -m "docs: add domain contract index"
```

### Task 2: 프로젝트와 이야기 설계 계약 작성

**Files:**

- Create: `docs/domains/projects.md`
- Create: `docs/domains/story-design.md`

**Interfaces:**

- Consumes: `frontend/src/modules/projects/domain/project.ts`, `frontend/src/modules/story-design/domain/story-concept.ts`와 해당 테스트.
- Produces: 프로젝트 메타데이터와 초기 이야기 콘셉트의 기술 중립적 계약.

- [ ] **Step 1: Projects 계약 작성**

`docs/domains/projects.md`를 다음 내용으로 작성한다.

```markdown
# Projects 도메인 계약

## 목적과 책임

Projects는 하나의 집필 작업을 식별하고 작품 서재에서 찾을 수 있게 하는 프로젝트 메타데이터를 소유한다. 이야기의 실제 내용은 소유하지 않는다.

## 보편 언어

- **프로젝트:** 하나의 작품을 기획하고 집필하는 작업 단위
- **프로젝트 식별자:** 프로젝트를 다른 작업과 구분하는 고유 값
- **제목:** 작품 서재와 집필 작업공간에서 사용하는 프로젝트 이름
- **로그라인:** 작품의 핵심 갈등과 관계를 한 문장으로 요약한 설명
- **트로프 참조:** Story Design에서 선택한 로맨스 트로프의 식별자
- **최근 활동 시각:** 프로젝트 목록의 최근 작업 순서를 결정하는 값

## 핵심 모델

프로젝트는 프로젝트 식별자, 제목, 로그라인, 트로프 참조, 최근 활동 시각으로 구성된다. 프로젝트 식별자는 생성 후 같은 프로젝트를 참조하는 다른 도메인에서 공유한다.

## 불변 조건

- 제목은 앞뒤 공백을 제거한 뒤 비어 있어서는 안 된다.
- 로그라인은 저장 전에 앞뒤 공백을 제거해야 한다.
- 프로젝트 목록을 최근순으로 요청하면 최근 활동 시각이 큰 프로젝트가 먼저 와야 한다.
- 최근순 정렬은 입력 프로젝트 목록을 직접 변경해서는 안 된다.

## 유스케이스

### 프로젝트 생성

제목과 로그라인을 정규화하고 유효한 프로젝트 메타데이터를 반환한다. 제목이 비어 있으면 생성을 거부한다.

### 최근 프로젝트 조회

프로젝트 목록을 최근 활동 시각의 내림차순으로 정렬한 새 목록을 반환한다.

## 입력과 출력

- Story Design에서 선택한 트로프 식별자와 로그라인을 입력받는다.
- 애플리케이션 유스케이스에서 프로젝트 식별자와 현재 시각을 입력받는다.
- 생성된 프로젝트 식별자를 Story Design, Story Bible, Manuscript의 연관 기준으로 제공한다.
- 원고 저장이 완료되면 애플리케이션 유스케이스로부터 갱신된 최근 활동 시각을 전달받는다.

## 책임지지 않는 영역

- 트로프의 유효성 및 콘셉트 검증
- 인물과 세계관 정보
- 장면과 원고 텍스트
- 집필 제안 생성 또는 적용
```

- [ ] **Step 2: Story Design 계약 작성**

`docs/domains/story-design.md`를 다음 내용으로 작성한다.

```markdown
# Story Design 도메인 계약

## 목적과 책임

Story Design은 로맨스 이야기의 출발점을 정의한다. 선택 가능한 로맨스 트로프와 프로젝트를 시작하기 위한 최소 이야기 콘셉트를 소유하고 검증한다.

## 보편 언어

- **트로프:** 독자가 기대하는 관계의 출발점과 감정 전개 유형
- **트로프 템플릿:** 트로프 식별자, 제목, 요약, 태그, 시작 로그라인으로 구성된 선택지
- **이야기 콘셉트:** 트로프, 로그라인, 두 주인공 이름을 프로젝트와 연결한 초기 설계
- **주인공 이름:** 초기 Story Bible을 만들 때 사용하는 두 인물의 이름

## 핵심 모델

트로프 템플릿은 선택 가능한 로맨스 유형을 설명한다. 이야기 콘셉트는 콘셉트 식별자와 프로젝트 식별자, 트로프 식별자, 로그라인, 정확히 두 명의 주인공 이름을 가진다.

현재 제공하는 트로프는 앙숙에서 연인으로, 계약 연애, 재회 로맨스, 친구에서 연인으로다.

## 불변 조건

- 이야기 콘셉트는 등록된 트로프만 참조해야 한다.
- 이야기 콘셉트에는 정확히 두 명의 주인공 이름이 있어야 한다.
- 두 주인공 이름은 앞뒤 공백을 제거한 뒤 모두 비어 있지 않아야 한다.
- 로그라인은 저장 전에 앞뒤 공백을 제거해야 한다.
- 등록되지 않은 트로프를 조회하거나 참조하면 요청을 거부해야 한다.

## 유스케이스

### 트로프 조회

트로프 식별자에 해당하는 등록된 템플릿을 반환한다. 일치하는 템플릿이 없으면 조회를 거부한다.

### 이야기 콘셉트 생성

트로프와 두 주인공을 검증하고 이름과 로그라인을 정규화한 이야기 콘셉트를 반환한다.

## 입력과 출력

- 사용자 선택으로부터 트로프 식별자, 로그라인, 두 주인공 이름을 입력받는다.
- Projects에서 생성된 프로젝트 식별자를 입력받는다.
- 검증된 트로프 식별자와 로그라인을 Projects의 프로젝트 메타데이터 생성에 제공한다.
- 검증된 두 주인공 이름을 Story Bible의 초기 인물 생성에 제공한다.

## 책임지지 않는 영역

- 프로젝트 목록과 최근 활동 순서
- 인물의 욕망, 숨은 감정, 세계관 세부 정보
- 장면 구성과 원고 텍스트
- 집필 제안 생성
```

- [ ] **Step 3: 구현과 불변 조건 대조**

Run:

```sh
rg -n "trim|toThrow|sortProjectsByRecent|getTropeTemplate|protagonistNames" frontend/src/modules/projects frontend/src/modules/story-design
```

Expected: 문서에 기록한 제목·로그라인·이름 정규화, 트로프 검증, 최근순 정렬을 뒷받침하는 구현과 테스트가 출력된다.

- [ ] **Step 4: 프로젝트와 설계 계약 커밋**

```sh
git add docs/domains/projects.md docs/domains/story-design.md
git commit -m "docs: define project and story design contracts"
```

### Task 3: 집필 문맥과 원고, 지원 계약 작성

**Files:**

- Create: `docs/domains/story-bible.md`
- Create: `docs/domains/manuscript.md`
- Create: `docs/domains/writing-assistant.md`

**Interfaces:**

- Consumes: Story Bible, Manuscript, Writing Assistant 도메인 구현과 `create-project`, `apply-writing-suggestion` 애플리케이션 유스케이스.
- Produces: 집필 문맥, 원고 소유권, 요청형 지원에 대한 기술 중립적 계약.

- [ ] **Step 1: Story Bible 계약 작성**

`docs/domains/story-bible.md`를 다음 내용으로 작성한다.

```markdown
# Story Bible 도메인 계약

## 목적과 책임

Story Bible은 작품 안에서 사실로 취급되는 인물과 세계관의 기준 정보를 소유한다. 집필 장면에 필요한 정보만 선택해 문맥으로 제공한다.

## 보편 언어

- **스토리 바이블:** 프로젝트에 속한 인물과 세계관 기준 정보의 모음
- **인물:** 이름, 역할, 욕망, 숨은 감정을 가진 이야기 참여자
- **욕망:** 인물이 겉으로 이루고 싶어 하는 목표
- **숨은 감정:** 인물이 직접 드러내지 않지만 행동과 대사에 영향을 주는 마음
- **세계관 항목:** 장소, 사물, 규칙 중 하나로 분류되는 작품 속 기준 정보
- **장면 문맥 참조:** 장면과 관련된 인물 및 세계관 항목 식별자 목록
- **장면 문맥:** 유효한 참조에 해당하는 인물과 세계관 정보의 부분집합

## 핵심 모델

스토리 바이블은 프로젝트 식별자, 인물 목록, 세계관 항목 목록으로 구성된다. 인물은 고유 식별자와 이름, 역할, 욕망, 숨은 감정을 가진다. 세계관 항목은 고유 식별자와 분류, 제목, 설명을 가진다.

## 불변 조건

- 스토리 바이블은 하나의 프로젝트에 속해야 한다.
- 초기 스토리 바이블은 Story Design에서 검증한 두 주인공을 인물로 만들어야 한다.
- 인물과 세계관 항목은 프로젝트 안에서 식별 가능한 값을 가져야 한다.
- 장면 문맥에는 참조 식별자와 일치하는 인물과 세계관 항목만 포함해야 한다.
- 존재하지 않는 참조 식별자는 결과에서 제외해야 하며 기준 정보를 새로 만들거나 변경해서는 안 된다.

## 유스케이스

### 초기 스토리 바이블 생성

프로젝트 식별자와 두 주인공 이름으로 초기 인물 정보와 첫 세계관 항목을 만든다.

### 장면 문맥 선택

장면이 참조하는 인물과 세계관 식별자를 받아 스토리 바이블에 존재하는 정보만 반환한다.

## 입력과 출력

- Projects에서 생성된 프로젝트 식별자를 입력받는다.
- Story Design에서 검증된 두 주인공 이름을 입력받는다.
- Manuscript 장면이 보유한 관련 인물 및 세계관 식별자를 입력받는다.
- 선택한 장면 문맥을 집필 화면과 Writing Assistant 요청 구성에 제공한다.

## 책임지지 않는 영역

- 프로젝트 제목과 최근 활동 시각
- 이야기 트로프와 초기 콘셉트 검증
- 장면 순서와 원고 텍스트
- 집필 제안 생성과 적용
```

- [ ] **Step 2: Manuscript 계약 작성**

`docs/domains/manuscript.md`를 다음 내용으로 작성한다.

```markdown
# Manuscript 도메인 계약

## 목적과 책임

Manuscript는 프로젝트의 장면과 원고 텍스트를 소유한다. 원고 내용의 삽입, 교체, 전체 갱신은 Manuscript의 규칙을 통해서만 수행한다.

## 보편 언어

- **원고:** 프로젝트에 속한 장면의 모음과 현재 활성 장면 상태
- **장면:** 장 번호, 제목, 본문, 관련 인물 및 세계관 참조를 가진 집필 단위
- **활성 장면:** 현재 집필 대상으로 선택된 장면
- **커서 위치:** 장면 본문에서 새 텍스트를 삽입할 문자 위치
- **텍스트 범위:** 시작 위치를 포함하고 끝 위치 직전까지를 나타내는 선택 구간
- **관련 문맥 참조:** 장면과 관련된 Story Bible 항목의 식별자

## 핵심 모델

원고는 원고 식별자, 프로젝트 식별자, 장면 목록, 활성 장면 식별자로 구성된다. 장면은 장면 식별자, 제목, 장 번호, 본문, 관련 인물 식별자 목록, 관련 세계관 식별자 목록을 가진다.

## 불변 조건

- 원고는 하나의 프로젝트에 속해야 한다.
- 활성 장면 식별자는 원고에 존재하는 장면을 가리켜야 한다.
- 장면 본문을 갱신하려면 해당 장면이 원고에 존재해야 한다.
- 커서 위치는 0 이상 본문 길이 이하여야 한다.
- 텍스트 범위는 `0 ≤ 시작 ≤ 끝 ≤ 본문 길이`를 만족해야 한다.
- 원고 변경은 입력 원고를 직접 변경하지 않고 변경된 새 원고를 반환해야 한다.
- 원고 텍스트는 Manuscript 이외의 도메인이 직접 변경해서는 안 된다.

## 유스케이스

### 초기 원고 생성

프로젝트 식별자를 받아 첫 장면과 그 장면을 가리키는 활성 장면 상태를 만든다.

### 장면 본문 갱신

존재하는 장면의 본문 전체를 새 내용으로 교체한 원고를 반환한다.

### 커서 위치에 텍스트 삽입

유효한 커서 위치에 새 텍스트를 삽입한 본문을 반환한다.

### 선택 범위 교체

유효한 텍스트 범위를 새 텍스트로 교체한 본문을 반환한다.

## 입력과 출력

- Projects에서 생성된 프로젝트 식별자를 입력받는다.
- Story Bible을 참조할 인물과 세계관 항목 식별자를 장면에 보관한다.
- Writing Assistant의 삽입 또는 교체 제안을 애플리케이션 유스케이스를 통해 입력받는다.
- 현재 장면 본문과 관련 문맥 참조를 집필 지원 요청 구성에 제공한다.

## 책임지지 않는 영역

- 프로젝트 메타데이터와 트로프 검증
- 인물 및 세계관 정보의 내용
- 집필 제안 생성
- 제안을 사용자에게 표시하고 적용 여부를 결정하는 과정
```

- [ ] **Step 3: Writing Assistant 계약 작성**

`docs/domains/writing-assistant.md`를 다음 내용으로 작성한다.

```markdown
# Writing Assistant 도메인 계약

## 목적과 책임

Writing Assistant는 사용자가 명시적으로 요청한 집필 지원 작업과 그 결과인 제안을 소유한다. 원고를 자동으로 읽거나 변경하지 않으며, 제안 적용 여부는 이 도메인 밖에서 결정한다.

## 보편 언어

- **집필 지원 요청:** 작업 종류와 현재 장면 문맥을 결합한 명시적 요청
- **이어 쓰기:** 현재 감정선을 유지하는 다음 문단 삽입 제안
- **문장 다듬기:** 사용자가 선택한 문장을 다른 표현으로 교체하는 제안
- **대사 제안:** 인물 이름과 현재 문맥을 활용한 대화 삽입 제안
- **일관성 검사:** 원고를 변경하지 않고 인물, 장소, 시간, 감정선의 문제를 알리는 진단
- **제안:** 삽입, 교체, 진단 중 하나의 적용 방식을 가진 결과

## 핵심 모델

집필 지원 요청은 작업 종류, 장면 본문, 선택한 텍스트, 인물 이름 목록으로 구성된다. 제안은 제안 식별자, 요청 작업, 적용 방식, 제목, 내용으로 구성된다.

지원 작업은 이어 쓰기, 문장 다듬기, 대사 제안, 일관성 검사다. 적용 방식은 삽입, 교체, 진단이다.

## 불변 조건

- 사용자의 명시적 요청이 있어야 제안을 생성해야 한다.
- 문장 다듬기는 앞뒤 공백을 제거한 선택 텍스트가 있을 때만 요청할 수 있다.
- 이어 쓰기와 대사 제안은 삽입 제안을 반환해야 한다.
- 문장 다듬기는 교체 제안을 반환해야 한다.
- 일관성 검사는 진단 제안을 반환해야 하며 원고를 변경해서는 안 된다.
- 제안 생성은 전달받은 장면 본문을 직접 변경해서는 안 된다.
- 인물 이름이 부족하면 일반 역할명으로 대체할 수 있어야 한다.

## 유스케이스

### 집필 제안 생성

요청 작업과 전달받은 문맥을 사용해 삽입, 교체, 진단 중 하나의 제안을 반환한다. 필요한 선택 텍스트가 없으면 문장 다듬기 요청을 거부한다.

## 입력과 출력

- Manuscript의 현재 장면 본문을 애플리케이션 유스케이스를 통해 입력받는다.
- 선택된 원고 텍스트와 Story Bible에서 선택한 인물 이름을 입력받는다.
- 삽입, 교체, 진단 제안을 애플리케이션 유스케이스에 반환한다.
- 삽입과 교체 제안은 사용자가 적용을 요청한 경우에만 Manuscript로 전달된다.

## 책임지지 않는 영역

- 원고 텍스트의 소유와 직접 변경
- 장면의 커서 및 선택 범위 유효성 검증
- 인물과 세계관 기준 정보 관리
- 자동 실행, 백그라운드 원고 분석, 제안 자동 적용
```

- [ ] **Step 4: 모든 계약과 구현 대조**

Run:

```sh
rg -n "selectSceneContext|updateSceneContent|insertText|replaceTextRange|createWritingSuggestion|diagnostic|invalidSelection" frontend/src/modules frontend/src/features
```

Expected: 장면 문맥 필터링, 원고 범위 검증, 제안 종류, 진단 미적용 규칙을 뒷받침하는 구현이 출력된다.

- [ ] **Step 5: 문서 구조와 기술 중립성 검증**

Run:

```sh
rg --files docs/domains
rg -l "^## 목적과 책임" docs/domains/*.md
rg -n "React|localStorage|Vite|FastAPI|Django|Flask|데이터베이스|API 경로" docs/domains
git diff --check
```

Expected:

- `README.md`와 다섯 도메인 계약 파일이 출력된다.
- 다섯 도메인 계약 모두 `목적과 책임` 절을 가진다.
- 기술 및 프레임워크 종속 용어 검색 결과가 없다.
- `git diff --check`가 오류 없이 종료된다.

- [ ] **Step 6: 기존 프런트엔드 검증**

Run from `frontend/`:

```sh
mise exec -- pnpm check
```

Expected: 포맷, Oxlint, TypeScript와 36개 테스트가 모두 통과한다.

- [ ] **Step 7: 집필 계약 커밋**

```sh
git add docs/domains/story-bible.md docs/domains/manuscript.md docs/domains/writing-assistant.md
git commit -m "docs: define writing domain contracts"
```
