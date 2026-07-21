# Writing Workspace Reload Restoration Playwright Test Plan

## Application Overview

Bounded Playwright regression plan for only `/projects/silver-garden/write`, based on `docs/superpowers/specs/2026-07-21-writing-editor-reload-restoration-design.md` and `docs/superpowers/plans/2026-07-21-writing-editor-reload-restoration.md`. Every test starts from a blank/fresh browser context and may run independently in any order. Observe `GET /api/projects/silver-garden/workspace` and `PUT /api/manuscripts/silver-garden-manuscript` to prove exact manuscript and revision behavior. Generator target: `frontend/writing-workspace-reload.spec.ts`. Explicit exclusions: all scroll assertions and all ticket-worker #1 coverage; do not test failure/conflict/corrupt-snapshot behavior or any other route.

## Test Scenarios

### 1. Same-context autosave and full-reload restoration

**Seed:** `No seed file; start each test in a fresh browser context and navigate directly to /projects/silver-garden/write`

#### 1.1. Autosave followed by a full reload restores the unique marker and revision 2

**File:** `frontend/writing-workspace-reload.spec.ts`

**Steps:**

1. Create a fresh browser context and page, register observers for workspace GETs and manuscript PUTs, and navigate directly to `/projects/silver-garden/write`. - expect: The writing workspace loads successfully. - expect: The initial `GET /api/projects/silver-garden/workspace` response reports `manuscriptRevision: 1`. - expect: The `원고 본문` textbox contains the seed active-scene content and the `자동 저장됨` status is visible.
2. Append a deterministic unique marker such as `\n[e2e-reload-marker]` to the existing `원고 본문` value, preserving all seed text. - expect: The status progresses through `편집 중`, then `저장 중`, then `자동 저장됨` after the 800ms idle autosave. - expect: Exactly one successful `PUT /api/manuscripts/silver-garden-manuscript` for this edit is observed. - expect: The PUT request manuscript active-scene content ends with the unique marker and uses `expectedRevision: 1`. - expect: The PUT response is HTTP 200 and reports `manuscriptRevision: 2`.
3. Perform a real full-page reload with `page.reload()`, wait for the reloaded workspace GET and the editor to finish loading, then read the textbox value. - expect: The reloaded `GET /api/projects/silver-garden/workspace` response reports `manuscriptRevision: 2`. - expect: The GET manuscript active-scene content and the `원고 본문` textbox both contain the unique marker. - expect: The full textbox value exactly equals the content returned for the active scene. - expect: Failure condition: the seed-only text returns, the marker is absent, or the revision is not 2.

#### 1.2. The first save after reload sends expectedRevision 2 and returns revision 3

**File:** `frontend/writing-workspace-reload.spec.ts`

**Steps:**

1. In a fresh browser context, navigate to `/projects/silver-garden/write`, append a unique setup marker, wait for the successful autosave response at revision 2, then perform a real full-page reload and confirm the workspace GET restores that marker with `manuscriptRevision: 2`. - expect: The independent setup reaches a persisted revision-2 manuscript before the behavior under test begins. - expect: After reload, the textbox exactly matches the restored revision-2 active-scene content.
2. Append one additional deterministic character to the restored textbox value, register the PUT observer before editing, and wait for the autosave to complete. - expect: The autosave status progresses through `편집 중`, `저장 중`, and `자동 저장됨`. - expect: The next PUT request contains the newly edited manuscript and sends `expectedRevision: 2`. - expect: The PUT response is HTTP 200 and reports `manuscriptRevision: 3`. - expect: Failure condition: the request falls back to expected revision 1, conflicts, or the response revision is not 3.

#### 1.3. Empty manuscript content survives autosave and full reload exactly

**File:** `frontend/writing-workspace-reload.spec.ts`

**Steps:**

1. In a fresh browser context, navigate to `/projects/silver-garden/write`, register the manuscript PUT observer, and replace the `원고 본문` value with the empty string. - expect: The UI treats the empty value as an edit and progresses through `편집 중`, `저장 중`, and `자동 저장됨`. - expect: The successful PUT request carries an empty string for the active scene content with `expectedRevision: 1`. - expect: The PUT response reports `manuscriptRevision: 2`.
2. Perform a real full-page reload, wait for the workspace GET and editor load, and assert the textbox value with an exact empty-string assertion. - expect: The reloaded workspace GET reports `manuscriptRevision: 2` and an empty active-scene content string. - expect: The `원고 본문` textbox value is exactly `""`; whitespace, seed fallback text, and missing-value coercion all fail the test.

#### 1.4. Long multiline manuscript content survives autosave and full reload byte-for-string exactly

**File:** `frontend/writing-workspace-reload.spec.ts`

**Steps:**

1. In a fresh browser context, navigate to `/projects/silver-garden/write` and build a deterministic long multiline string with several thousand characters, Korean and ASCII text, explicit blank lines, punctuation, and unique beginning/end sentinels; do not perform or assert any scrolling. - expect: The fixture is deterministic and retains its exact newline placement for direct equality checks.
2. Register the PUT observer, replace the textbox value with the long multiline fixture, and wait for the autosave to finish. - expect: The autosave reaches `자동 저장됨` after the expected editing and saving states. - expect: The successful PUT request active-scene content exactly equals the fixture and sends `expectedRevision: 1`. - expect: The PUT response reports `manuscriptRevision: 2`.
3. Perform a real full-page reload, wait for the workspace GET and editor load, and compare both the response active-scene content and textbox value directly with the original fixture. - expect: The workspace GET reports `manuscriptRevision: 2`. - expect: Both restored strings exactly equal the original fixture, including every newline, blank line, Unicode character, and final sentinel. - expect: No scroll position, document scrolling, overflow, or ticket-worker #1 assertion is made.

### 2. Browser-context isolation

**Seed:** `No seed file; create two genuinely separate fresh browser contexts`

#### 2.1. A new browser context starts from the seed manuscript at revision 1

**File:** `frontend/writing-workspace-reload.spec.ts`

**Steps:**

1. Create browser context A, navigate to `/projects/silver-garden/write`, append a unique context-A marker, and wait for its successful autosave response at revision 2. - expect: Context A's PUT succeeds with `expectedRevision: 1` and response `manuscriptRevision: 2`. - expect: Context A contains the unique marker, establishing non-seed session state.
2. Create a genuinely new browser context B (not merely a new page or tab in context A), register the initial workspace GET observer, and navigate context B directly to `/projects/silver-garden/write`. - expect: Context B's initial workspace GET reports `manuscriptRevision: 1`. - expect: Context B's textbox exactly equals the active seed scene content returned by that GET. - expect: Context B does not contain context A's unique marker. - expect: Failure condition: context B inherits revision 2 or any manuscript content from context A.
3. Close both contexts without adding scroll assertions or exercising any other route. - expect: The test leaves no shared browser-context state for later tests.
