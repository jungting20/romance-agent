# 집필 화면 컴포넌트 버그 탐색 체크리스트

대상 경로: `/projects/silver-garden/write`

공용 UI 프리미티브와 Lucide 아이콘은 아래 애플리케이션 컴포넌트를 검증할 때 함께 확인한다.

## 화면 구성

- [x] `WritingWorkspacePage`
- [x] `LoadedWritingWorkspace`
- [x] `ContextPanelContent`
- [x] `AutosaveIndicator`

## 원고 편집

- [x] `ManuscriptEditor`
- [x] `SceneTitleField`
- [x] `SceneTree`

## 인물·세계관·AI 패널

- [x] `StoryContextPanel`
- [x] `WritingToolPanel`

## 인물 편집 오버레이

- [x] `CharacterCardEditorSheet`
- [x] `CharacterDiscardDialog`

## 세계관 편집 오버레이

- [x] `WorldEditorSheet`
- [x] `WorldEditorInitializingSheet`
- [x] `WorldDiscardDialog`
- [x] `WorldEntryFields`
- [x] `WorldEditorFeedback`

## 원고 충돌 오버레이

- [x] `ManuscriptConflictDialog`

## 완료 기준

- 각 컴포넌트의 지정 사용자 흐름을 실제 브라우저에서 확인한다.
- 발견한 결함은 깨끗한 상태에서 두 번 재현한다.
- 기존 티켓과 중복 여부를 확인한다.
- 재현 가능한 신규 결함만 `ticket-worker`에 등록한다.
- 컴포넌트별 한글 HTML 보고서와 필요한 증거 자료를 `docs/bug-reports/`에 남긴다.
