# Frontend Page Boundary Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the project setup page a thin composition boundary and make new page-owned transport, draft-state, and unsafe-cast violations fail frontend checks.

**Architecture:** Story Design becomes the authoritative owner of `TropeId`; the existing create-project feature owns the setup draft, submitted snapshot, mutation request, and transport-error translation; and `SetupPage` retains only route validation, screen composition, and success navigation. Oxlint provides immediate page-boundary feedback, while a TypeScript-AST Vitest test freezes the exact writing-workspace legacy baseline and rejects new violations.

**Tech Stack:** React 19, TypeScript 7, TanStack Router, TanStack Query v5, Oxlint 1.73, Vitest 4, Testing Library, MSW 2, Playwright 1.61, existing shadcn/ui components

## Global Constraints

- Authoritative design: `docs/superpowers/specs/2026-07-20-frontend-page-boundary-enforcement-design.md`.
- Approved unchanged API baseline: `docs/api/openapi.yaml` blob `69d64146d62ab12b7462839a1f3ef0f76133374d`, operationId `createProjectWorkspace`.
- Relevant domain contracts: `docs/domains/projects.md` and `docs/domains/story-design.md`; align implementation to them without changing their meaning or files.
- Do not edit `docs/api/openapi.yaml`, backend files, or `docs/domains/*.md`.
- Do not add a dependency.
- Do not introduce a reducer or duplicate TanStack Query pending, error, or success state.
- Do not refactor `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`; register only its exact frozen boundary baseline.
- Preserve the current setup screen layout and responsive behavior; change only the approved ownership, validation, copy, error-lifetime, typing, and accessibility behavior.
- Reuse the installed `Badge`, `Button`, `Card`, `Input`, `Label`, and `Textarea` components; no shadcn/ui installation or new primitive is required.
- Use branch name `feature/프론트엔드-페이지-경계` if implementation creates a worktree.
- Run frontend commands from `frontend/` through `mise exec -- pnpm ...`.
- Dispatch Tasks 2-5 sequentially to the project-scoped `.codex/agents/frontend.toml` implementer with the exact task paths; do not allow overlapping agents to edit the same file.
- Treat the UI plan, implementation, E2E planning/generation, frontend review, accepted-finding repair, and final verification as one indivisible frontend delivery.

---

## File Structure

Create:

- `frontend/docs/ui-plans/project-setup-page-boundary.md` — approved screen behavior and review baseline for the setup screen.
- `frontend/src/features/create-project/project-setup-state.ts` — pure draft updates and submitted-snapshot-aware transport error projection.
- `frontend/src/features/create-project/project-setup-state.test.ts` — pure state and error-lifetime tests.
- `frontend/src/features/create-project/use-project-setup.ts` — one project-setup workflow hook over TanStack Query.
- `frontend/src/features/create-project/ui/project-setup-form.tsx` — accessible project setup form presentation.
- `frontend/.oxlintrc.json` — page import and local-state ownership restrictions.
- `frontend/src/architecture/page-boundaries.test.ts` — AST enforcement and exact legacy baseline.
- `frontend/docs/e2e/project-setup-page-boundary-test-plan.md` — planner-approved browser scenarios.
- `frontend/project-setup-page-boundary.spec.ts` — generated Playwright coverage.

Modify:

- `frontend/src/modules/story-design/domain/story-concept.ts` — authoritative `TropeId`, templates, guard, and typed story concept.
- `frontend/src/modules/story-design/domain/story-concept.test.ts` — identifier guard and normalization coverage.
- `frontend/src/modules/story-design/ui/trope-selector.tsx` — remove icon-key assertion.
- `frontend/src/app/infrastructure/api/contracts.ts` — consume and re-export the domain-owned `TropeId`.
- `frontend/src/mocks/handlers/projects.ts` — consume the authoritative trope guard.
- `frontend/src/routes/new_.setup.tsx` — validate search through `isTropeId`.
- `frontend/src/features/create-project/create-project.ts` — type feature input with `TropeId`.
- `frontend/src/features/create-project/index.ts` — export the setup hook, controller type, and form.
- `frontend/src/pages/new-project/setup-page.tsx` — thin route-aware composition.
- `frontend/src/pages/new-project/setup-page.test.tsx` — observable validation, error-lifetime, accessibility, redirect, and regression coverage.
- `frontend/docs/frontend-coding-rules.md` — normative page boundary, form contract, error lifetime, reducer, and exception rules.
- `frontend/playwright.config.ts` — deterministic local web server and base URL for generated E2E tests.

Do not modify:

- `frontend/src/pages/writing-workspace/writing-workspace-page.tsx`.
- `docs/api/openapi.yaml`.
- `docs/domains/projects.md`.
- `docs/domains/story-design.md`.

---

### Task 1: Produce and Approve the Setup Screen UI Plan

**Files:**
- Create: `frontend/docs/ui-plans/project-setup-page-boundary.md`
- Read: `docs/superpowers/specs/2026-07-20-frontend-page-boundary-enforcement-design.md`
- Read: `docs/domains/projects.md`
- Read: `docs/domains/story-design.md`
- Read: `docs/api/openapi.yaml`

**Interfaces:**
- Consumes: approved design and unchanged `createProjectWorkspace` baseline.
- Produces: exact UI review baseline for route `/new/setup`, supplied to the frontend implementer, E2E planner/generator, and `frontend-review` agent.

- [ ] **Step 1: Assign the UI plan to the project UI-planning agent**

Assign only `frontend/docs/ui-plans/project-setup-page-boundary.md`. Require the plan to record this exact screen contract:

```text
Route example: /new/setup?trope=reunion; every accepted trope value is a validated TropeId
Visual scope: preserve the current desktop/mobile layout and styling
Page responsibility: route guard, selected-trope summary composition, success navigation
Feature responsibility: setup draft, submitted snapshot, mutation, transport-error projection
Form responsibility: title, optional logline, two required protagonist names, pending state, field/form feedback
Existing shadcn/ui status: Badge, Button, Card, Input, Label, Textarea are installed and must be reused
Adoption candidates: none
Accessibility: fieldset/legend for protagonists; associated descriptions and invalid state; async errors announced
Responsive behavior: unchanged from the current screen
API operation: createProjectWorkspace at blob 69d64146d62ab12b7462839a1f3ef0f76133374d
```

Expected: the agent edits only the assigned UI-plan path and returns its self-review handoff.

- [ ] **Step 2: Review and approve the exact UI plan baseline**

Confirm the written plan contains all values above, introduces no visual redesign or new component dependency, and maps every approved behavior to the setup screen. Record the approved file path and current blob:

```sh
git hash-object frontend/docs/ui-plans/project-setup-page-boundary.md
```

Expected: one non-empty blob hash; retain it for the implementation and review assignments.

- [ ] **Step 3: Commit the UI plan**

```sh
git add frontend/docs/ui-plans/project-setup-page-boundary.md
git commit -m "docs(frontend): plan project setup boundary UI"
```

Expected: one commit containing only the approved UI plan.

---

### Task 2: Make Story Design the Authoritative Trope Identifier Boundary

**Files:**
- Modify: `frontend/src/modules/story-design/domain/story-concept.test.ts`
- Modify: `frontend/src/modules/story-design/domain/story-concept.ts`
- Modify: `frontend/src/modules/story-design/ui/trope-selector.tsx`
- Modify: `frontend/src/app/infrastructure/api/contracts.ts`
- Modify: `frontend/src/mocks/handlers/projects.ts`
- Modify: `frontend/src/routes/new_.setup.tsx`
- Modify: `frontend/src/features/create-project/create-project.ts`

**Interfaces:**
- Consumes: the four trope identifiers already approved by `docs/domains/story-design.md` and OpenAPI.
- Produces: `TropeId`, `TROPE_IDS`, `isTropeId(value: unknown): value is TropeId`, and `TropeTemplate.id: TropeId` from `@/modules/story-design`.

- [ ] **Step 1: Add failing trope guard tests**

Add these tests to `frontend/src/modules/story-design/domain/story-concept.test.ts`:

```ts
test.each([
  "rivals-to-lovers",
  "contract-romance",
  "reunion",
  "friends-to-lovers",
])("recognizes the approved trope id %s", async (tropeId) => {
  const { isTropeId } = await import("./story-concept");

  expect(isTropeId(tropeId)).toBe(true);
});

test.each([undefined, null, 1, "unknown-trope"])(
  "rejects an unapproved trope id %s",
  async (value) => {
    const { isTropeId } = await import("./story-concept");

    expect(isTropeId(value)).toBe(false);
  },
);
```

- [ ] **Step 2: Run the focused test and verify the missing guard failure**

Run:

```sh
mise exec -- pnpm test --run src/modules/story-design/domain/story-concept.test.ts
```

Expected: FAIL because `isTropeId` is not exported.

- [ ] **Step 3: Add the authoritative type and guard**

Replace the broad template identifier definition at the top of
`frontend/src/modules/story-design/domain/story-concept.ts` with:

```ts
export const TROPE_IDS = [
  "rivals-to-lovers",
  "contract-romance",
  "reunion",
  "friends-to-lovers",
] as const;

export type TropeId = (typeof TROPE_IDS)[number];

export interface TropeTemplate {
  id: TropeId;
  title: string;
  summary: string;
  tags: string[];
  starterLogline: string;
}

export function isTropeId(value: unknown): value is TropeId {
  return typeof value === "string" && TROPE_IDS.some((tropeId) => tropeId === value);
}
```

Type the four existing template bodies with the authoritative identifier:

```ts
export const TROPE_TEMPLATES: TropeTemplate[] = [
  {
    id: "rivals-to-lovers",
    title: "앙숙에서 연인으로",
    summary: "부딪칠수록 선명해지는 마음",
    tags: ["긴장감", "티키타카", "느린 감정선"],
    starterLogline:
      "매번 승부를 겨루는 두 사람이 공동의 목표를 위해 손을 잡으며 서로의 진심을 발견한다.",
  },
  {
    id: "contract-romance",
    title: "계약 연애",
    summary: "거짓으로 시작한 관계의 진짜 감정",
    tags: ["가짜 연애", "가까운 거리", "비밀"],
    starterLogline:
      "서로의 필요 때문에 연인을 연기한 두 사람이 계약의 끝에서 진짜 마음을 마주한다.",
  },
  {
    id: "reunion",
    title: "재회 로맨스",
    summary: "끝내지 못한 사랑의 두 번째 기회",
    tags: ["과거", "오해", "두 번째 기회"],
    starterLogline:
      "오해로 헤어진 두 사람이 오래된 온실에서 다시 만나 미처 전하지 못한 진실을 마주한다.",
  },
  {
    id: "friends-to-lovers",
    title: "친구에서 연인으로",
    summary: "익숙한 사이에 번지는 낯선 설렘",
    tags: ["오랜 친구", "깨달음", "고백"],
    starterLogline:
      "오랜 친구였던 두 사람이 한 번의 약속을 계기로 서로를 새로운 눈으로 바라보기 시작한다.",
  },
];
```

Change the story concept and creation input boundary to:

```ts
export interface StoryConcept {
  id: string;
  projectId: string;
  tropeId: TropeId;
  logline: string;
  protagonistNames: [string, string];
}

export interface CreateStoryConceptInput extends Omit<
  StoryConcept,
  "tropeId" | "protagonistNames"
> {
  tropeId: string;
  protagonistNames: [string, string];
}
```

Inside `createStoryConcept`, retain runtime rejection and return the validated identifier:

```ts
const trope = getTropeTemplate(input.tropeId);
const protagonistNames = input.protagonistNames.map((name) => name.trim()) as [string, string];

if (protagonistNames.some((name) => !name)) {
  throw new Error("두 주인공의 이름을 모두 입력해 주세요.");
}

return {
  ...input,
  tropeId: trope.id,
  logline: input.logline.trim(),
  protagonistNames,
};
```

- [ ] **Step 4: Route all frontend trope consumers through the authoritative type**

At the top of `frontend/src/app/infrastructure/api/contracts.ts`, replace the local union with:

```ts
import type { TropeId } from "@/modules/story-design";

export type { TropeId } from "@/modules/story-design";
```

In `frontend/src/routes/new_.setup.tsx`, import and use the guard:

```ts
import { isTropeId } from "@/modules/story-design";

export const Route = createFileRoute("/new_/setup")({
  validateSearch: (search: Record<string, unknown>) => ({
    trope: isTropeId(search.trope) ? search.trope : undefined,
  }),
  component: SetupPage,
});
```

In `frontend/src/features/create-project/create-project.ts`, import `TropeId` and narrow the feature input:

```ts
import { createStoryConcept, type StoryConcept, type TropeId } from "@/modules/story-design";

export interface CreateProjectFromTropeInput {
  title: string;
  logline: string;
  tropeId: TropeId;
  protagonistNames: [string, string];
}
```

In `frontend/src/mocks/handlers/projects.ts`, import `isTropeId` from the Story Design public API, remove `TropeId` from the transport import, and delete the local `tropeIds` array and local `isTropeId` function:

```ts
import { isTropeId } from "@/modules/story-design";
```

In `frontend/src/modules/story-design/ui/trope-selector.tsx`, remove the key assertion with an exhaustive typed icon map:

```ts
import {
  ArrowRight,
  Handshake,
  HeartHandshake,
  RefreshCcw,
  Swords,
  type LucideIcon,
} from "lucide-react";

import { TROPE_TEMPLATES, type TropeId } from "@/modules/story-design";

const icons = {
  "rivals-to-lovers": Swords,
  "contract-romance": Handshake,
  reunion: RefreshCcw,
  "friends-to-lovers": HeartHandshake,
} satisfies Record<TropeId, LucideIcon>;
```

Use `const Icon = icons[trope.id];` inside the map.

- [ ] **Step 5: Run focused tests and type checking**

Run:

```sh
mise exec -- pnpm test --run src/modules/story-design/domain/story-concept.test.ts src/features/create-project/create-project.test.ts src/mocks/project-handlers.test.ts
mise exec -- pnpm typecheck
```

Expected: all selected tests PASS and TypeScript exits 0.

- [ ] **Step 6: Commit the typed boundary**

```sh
git add frontend/src/modules/story-design frontend/src/app/infrastructure/api/contracts.ts frontend/src/mocks/handlers/projects.ts frontend/src/routes/new_.setup.tsx frontend/src/features/create-project/create-project.ts
git commit -m "refactor(frontend): centralize trope identifier validation"
```

Expected: the commit contains only the typed trope boundary and its tests.

---

### Task 3: Build Submitted-Snapshot-Aware Project Setup State

**Files:**
- Create: `frontend/src/features/create-project/project-setup-state.test.ts`
- Create: `frontend/src/features/create-project/project-setup-state.ts`

**Interfaces:**
- Consumes: `TropeId`, `CreateProjectRequest`, and `ApiRequestError` internally.
- Produces: `ProjectSetupDraft`, `ProjectSetupField`, `ProjectSetupErrors`, `createProjectSetupDraft`, `updateProjectSetupDraft`, `toCreateProjectRequest`, and `projectSetupErrors`.

- [ ] **Step 1: Write the failing pure state tests**

Create `frontend/src/features/create-project/project-setup-state.test.ts`:

```ts
import { describe, expect, test } from "vitest";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";

import {
  createProjectSetupDraft,
  projectSetupErrors,
  toCreateProjectRequest,
  updateProjectSetupDraft,
} from "./project-setup-state";

describe("project setup state", () => {
  test("creates the approved initial draft", () => {
    expect(createProjectSetupDraft("트로프 시작 문장")).toEqual({
      title: "",
      logline: "트로프 시작 문장",
      protagonistNames: ["서윤", "도현"],
    });
  });

  test("updates one protagonist without mutating the previous draft", () => {
    const previous = createProjectSetupDraft("로그라인");
    const next = updateProjectSetupDraft(previous, "firstProtagonist", "하린");

    expect(next.protagonistNames).toEqual(["하린", "도현"]);
    expect(previous.protagonistNames).toEqual(["서윤", "도현"]);
  });

  test("keeps an unchanged field error after another field changes", () => {
    const submitted = {
      title: "겹치는 제목",
      logline: "로그라인",
      protagonistNames: ["서윤", "도현"] as [string, string],
    };
    const current = updateProjectSetupDraft(submitted, "title", "새 제목");
    const error = new ApiRequestError(422, {
      code: "INVALID_PROTAGONISTS",
      message: "입력 내용을 확인해 주세요.",
      fieldErrors: [
        { path: "title", message: "이미 사용 중인 제목이에요." },
        { path: "protagonistNames", message: "두 이름을 확인해 주세요." },
      ],
    });

    expect(projectSetupErrors(error, current, submitted)).toEqual({
      protagonistNames: "두 이름을 확인해 주세요.",
    });
  });

  test("hides a form-level failure after any draft edit", () => {
    const submitted = createProjectSetupDraft("로그라인");
    const current = updateProjectSetupDraft(submitted, "title", "새 제목");
    const error = new ApiRequestError(500, {
      code: "INTERNAL_ERROR",
      message: "서버 실패",
      fieldErrors: [],
    });

    expect(projectSetupErrors(error, current, submitted)).toEqual({});
  });

  test("shows generic feedback for a non-contract failure", () => {
    const submitted = createProjectSetupDraft("로그라인");

    expect(projectSetupErrors(new Error("network failed"), submitted, submitted)).toEqual({
      form: "프로젝트를 만들지 못했어요. 잠시 후 다시 시도해 주세요.",
    });
  });

  test("serializes the typed transport request without a cast", () => {
    expect(
      toCreateProjectRequest(
        {
          title: "제목",
          logline: "",
          protagonistNames: ["서윤", "도현"],
        },
        "reunion",
      ),
    ).toEqual({
      title: "제목",
      logline: "",
      tropeId: "reunion",
      protagonistNames: ["서윤", "도현"],
    });
  });
});
```

- [ ] **Step 2: Run the focused test and verify the missing module failure**

Run:

```sh
mise exec -- pnpm test --run src/features/create-project/project-setup-state.test.ts
```

Expected: FAIL because `project-setup-state.ts` does not exist.

- [ ] **Step 3: Implement immutable draft updates and error projection**

Create `frontend/src/features/create-project/project-setup-state.ts`:

```ts
import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type { CreateProjectRequest } from "@/app/infrastructure/api/contracts";
import type { TropeId } from "@/modules/story-design";

export interface ProjectSetupDraft {
  title: string;
  logline: string;
  protagonistNames: [string, string];
}

export type ProjectSetupField =
  | "title"
  | "logline"
  | "firstProtagonist"
  | "secondProtagonist";

export interface ProjectSetupErrors {
  title?: string;
  logline?: string;
  protagonistNames?: string;
  form?: string;
}

const genericCreateProjectError =
  "프로젝트를 만들지 못했어요. 잠시 후 다시 시도해 주세요.";

export function createProjectSetupDraft(starterLogline: string): ProjectSetupDraft {
  return {
    title: "",
    logline: starterLogline,
    protagonistNames: ["서윤", "도현"],
  };
}

export function updateProjectSetupDraft(
  draft: ProjectSetupDraft,
  field: ProjectSetupField,
  value: string,
): ProjectSetupDraft {
  if (field === "title" || field === "logline") {
    return { ...draft, [field]: value };
  }

  return {
    ...draft,
    protagonistNames:
      field === "firstProtagonist"
        ? [value, draft.protagonistNames[1]]
        : [draft.protagonistNames[0], value],
  };
}

export function toCreateProjectRequest(
  draft: ProjectSetupDraft,
  tropeId: TropeId,
): CreateProjectRequest {
  return {
    title: draft.title,
    logline: draft.logline,
    tropeId,
    protagonistNames: draft.protagonistNames,
  };
}

export function projectSetupErrors(
  error: unknown,
  draft: ProjectSetupDraft,
  submittedDraft: ProjectSetupDraft | null,
): ProjectSetupErrors {
  if (!submittedDraft || !error) {
    return {};
  }

  const draftChanged = !sameDraft(draft, submittedDraft);

  if (!(error instanceof ApiRequestError)) {
    return draftChanged ? {} : { form: genericCreateProjectError };
  }

  if (error.status !== 422) {
    return draftChanged ? {} : { form: genericCreateProjectError };
  }

  const fieldErrors = error.error.fieldErrors;
  const title = sameTitle(draft, submittedDraft)
    ? fieldErrors.find(({ path }) => path === "title")?.message
    : undefined;
  const logline = sameLogline(draft, submittedDraft)
    ? fieldErrors.find(({ path }) => path === "logline")?.message
    : undefined;
  const protagonistNames = sameProtagonists(draft, submittedDraft)
    ? fieldErrors.find(({ path }) => path === "protagonistNames")?.message
    : undefined;
  const hasUnmappedField =
    fieldErrors.length === 0 ||
    fieldErrors.some(
      ({ path }) => !["title", "logline", "protagonistNames"].includes(path),
    );

  return compactErrors({
    title,
    logline,
    protagonistNames,
    form: hasUnmappedField && !draftChanged ? error.error.message : undefined,
  });
}

function sameDraft(left: ProjectSetupDraft, right: ProjectSetupDraft): boolean {
  return sameTitle(left, right) && sameLogline(left, right) && sameProtagonists(left, right);
}

function sameTitle(left: ProjectSetupDraft, right: ProjectSetupDraft): boolean {
  return left.title === right.title;
}

function sameLogline(left: ProjectSetupDraft, right: ProjectSetupDraft): boolean {
  return left.logline === right.logline;
}

function sameProtagonists(left: ProjectSetupDraft, right: ProjectSetupDraft): boolean {
  return (
    left.protagonistNames[0] === right.protagonistNames[0] &&
    left.protagonistNames[1] === right.protagonistNames[1]
  );
}

function compactErrors(errors: ProjectSetupErrors): ProjectSetupErrors {
  const compacted: ProjectSetupErrors = {};
  if (errors.title) compacted.title = errors.title;
  if (errors.logline) compacted.logline = errors.logline;
  if (errors.protagonistNames) compacted.protagonistNames = errors.protagonistNames;
  if (errors.form) compacted.form = errors.form;
  return compacted;
}
```

- [ ] **Step 4: Run the state tests and type checking**

Run:

```sh
mise exec -- pnpm test --run src/features/create-project/project-setup-state.test.ts
mise exec -- pnpm typecheck
```

Expected: all state tests PASS and TypeScript exits 0.

- [ ] **Step 5: Commit the pure setup state**

```sh
git add frontend/src/features/create-project/project-setup-state.ts frontend/src/features/create-project/project-setup-state.test.ts
git commit -m "feat(frontend): model project setup draft errors"
```

Expected: one independently passing pure-state commit.

---

### Task 4: Move the Setup Workflow and Form out of the Page

**Files:**
- Create: `frontend/src/features/create-project/use-project-setup.ts`
- Create: `frontend/src/features/create-project/ui/project-setup-form.tsx`
- Modify: `frontend/src/features/create-project/index.ts`
- Modify: `frontend/src/pages/new-project/setup-page.test.tsx`
- Modify: `frontend/src/pages/new-project/setup-page.tsx`

**Interfaces:**
- Consumes: `TropeId`, `useCreateProjectMutation`, and Task 3 state helpers.
- Produces: `useProjectSetup(options): ProjectSetupController` and `<ProjectSetupForm setup={controller} />` through `@/features/create-project`.

- [ ] **Step 1: Add failing page behavior tests**

Extend `frontend/src/pages/new-project/setup-page.test.tsx` with these observable cases. Change `renderSetup` to accept an initial entry while retaining its current default:

```ts
function renderSetup(initialEntry = "/new/setup?trope=reunion") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppMemoryRouter([initialEntry]);

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  return router;
}
```

Add these tests:

```ts
test("redirects an invalid trope search value to trope selection", async () => {
  const router = renderSetup("/new/setup?trope=unknown-trope");

  await waitFor(() => {
    expect(router.state.location.pathname).toBe("/new");
  });
});

test("allows the contract-optional logline to be empty", async () => {
  let submittedRequest: CreateProjectRequest | undefined;
  server.use(
    http.post("/api/projects", async ({ request }) => {
      submittedRequest = (await request.json()) as CreateProjectRequest;
      return HttpResponse.json(createWorkspace("blank-logline-project"), { status: 201 });
    }),
  );
  const user = userEvent.setup();
  renderSetup();

  await user.type(await screen.findByLabelText("작품 제목"), "빈 로그라인 이야기");
  await user.clear(screen.getByLabelText("한 줄 아이디어"));
  await user.click(screen.getByRole("button", { name: "작업 공간 열기" }));

  await waitFor(() => expect(submittedRequest?.logline).toBe(""));
});

test("keeps an unchanged protagonist error after the title changes", async () => {
  server.use(
    http.post("/api/projects", () =>
      HttpResponse.json(
        {
          code: "INVALID_PROTAGONISTS",
          message: "입력 내용을 확인해 주세요.",
          fieldErrors: [
            { path: "title", message: "이미 사용 중인 작품 제목이에요." },
            { path: "protagonistNames", message: "두 주인공의 이름을 확인해 주세요." },
          ],
        },
        { status: 422 },
      ),
    ),
  );
  const user = userEvent.setup();
  renderSetup();

  const title = await screen.findByLabelText("작품 제목");
  await user.type(title, "겹치는 제목");
  await user.click(screen.getByRole("button", { name: "작업 공간 열기" }));
  await screen.findByText("이미 사용 중인 작품 제목이에요.");

  await user.type(title, " 수정");

  expect(screen.queryByText("이미 사용 중인 작품 제목이에요.")).not.toBeInTheDocument();
  expect(screen.getByText("두 주인공의 이름을 확인해 주세요.")).toBeInTheDocument();
});

test("uses contract-consistent guidance and semantic protagonist grouping", async () => {
  renderSetup();

  expect(await screen.findByPlaceholderText("작품 제목을 입력해 주세요")).toBeRequired();
  expect(screen.getByLabelText("한 줄 아이디어")).not.toBeRequired();
  expect(screen.getByRole("group", { name: "두 주인공" })).toBeInTheDocument();
});
```

Update the existing field-error test to assert each asynchronously rendered error is exposed as an alert while retaining the existing accessible descriptions.

- [ ] **Step 2: Run the page tests and verify the approved behavior failures**

Run:

```sh
mise exec -- pnpm test --run src/pages/new-project/setup-page.test.tsx
```

Expected: FAIL because invalid search is only broadly typed, logline is required, all mutation errors reset on title edit, and protagonist inputs are not grouped by a fieldset.

- [ ] **Step 3: Implement the feature workflow hook**

Create `frontend/src/features/create-project/use-project-setup.ts`:

```ts
import { useState } from "react";

import { useCreateProjectMutation } from "@/features/project-persistence";
import type { TropeId } from "@/modules/story-design";

import {
  createProjectSetupDraft,
  type ProjectSetupDraft,
  type ProjectSetupErrors,
  type ProjectSetupField,
  projectSetupErrors,
  toCreateProjectRequest,
  updateProjectSetupDraft,
} from "./project-setup-state";

export interface UseProjectSetupOptions {
  tropeId: TropeId;
  starterLogline: string;
  onCreated: (projectId: string) => void | Promise<void>;
}

export interface ProjectSetupController {
  draft: ProjectSetupDraft;
  errors: ProjectSetupErrors;
  isPending: boolean;
  updateField: (field: ProjectSetupField, value: string) => void;
  submit: () => Promise<void>;
}

export function useProjectSetup({
  tropeId,
  starterLogline,
  onCreated,
}: UseProjectSetupOptions): ProjectSetupController {
  const createProject = useCreateProjectMutation();
  const [draft, setDraft] = useState(() => createProjectSetupDraft(starterLogline));
  const [submittedDraft, setSubmittedDraft] = useState<ProjectSetupDraft | null>(null);

  return {
    draft,
    errors: projectSetupErrors(createProject.error, draft, submittedDraft),
    isPending: createProject.isPending,
    updateField: (field, value) => {
      setDraft((current) => updateProjectSetupDraft(current, field, value));
    },
    submit: async () => {
      if (createProject.isPending) return;

      const snapshot: ProjectSetupDraft = {
        ...draft,
        protagonistNames: [draft.protagonistNames[0], draft.protagonistNames[1]],
      };
      setSubmittedDraft(snapshot);

      try {
        const workspace = await createProject.mutateAsync(
          toCreateProjectRequest(snapshot, tropeId),
        );
        await onCreated(workspace.project.id);
      } catch {
        // The controller projects mutation errors into field and form feedback.
      }
    },
  };
}
```

- [ ] **Step 4: Create the accessible feature-owned form**

Create `frontend/src/features/create-project/ui/project-setup-form.tsx` with the existing Card/form styling and this complete behavior:

```tsx
import { type FormEvent } from "react";
import { ArrowRight, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import type { ProjectSetupController } from "../use-project-setup";

export interface ProjectSetupFormProps {
  setup: ProjectSetupController;
}

export function ProjectSetupForm({ setup }: ProjectSetupFormProps) {
  const { draft, errors, isPending, updateField, submit } = setup;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit();
  }

  return (
    <Card className="border-border/70 bg-card px-1 py-2 shadow-[0_28px_90px_-55px_rgba(75,45,34,0.6)] sm:px-4 sm:py-5">
      <CardContent>
        <form
          aria-label="새 프로젝트 설정"
          aria-busy={isPending}
          className="space-y-7"
          onSubmit={handleSubmit}
        >
          <div className="space-y-2.5">
            <Label htmlFor="project-title">작품 제목</Label>
            <Input
              id="project-title"
              aria-describedby={errors.title ? "project-title-error" : undefined}
              aria-invalid={errors.title ? true : undefined}
              value={draft.title}
              onChange={(event) => updateField("title", event.target.value)}
              placeholder="작품 제목을 입력해 주세요"
              required
              disabled={isPending}
              className="h-11 bg-background/60"
            />
            {errors.title && (
              <p id="project-title-error" role="alert" className="text-sm text-destructive">
                {errors.title}
              </p>
            )}
          </div>

          <div className="space-y-2.5">
            <Label htmlFor="project-logline">한 줄 아이디어</Label>
            <Textarea
              id="project-logline"
              aria-describedby={
                errors.logline
                  ? "project-logline-help project-logline-error"
                  : "project-logline-help"
              }
              aria-invalid={errors.logline ? true : undefined}
              value={draft.logline}
              onChange={(event) => updateField("logline", event.target.value)}
              rows={4}
              disabled={isPending}
              className="resize-none bg-background/60 leading-6"
            />
            {errors.logline && (
              <p id="project-logline-error" role="alert" className="text-sm text-destructive">
                {errors.logline}
              </p>
            )}
            <p
              id="project-logline-help"
              className="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <Sparkles className="size-3.5 text-primary" /> 선택한 트로프에서 시작 문장을
              준비했어요.
            </p>
          </div>

          <fieldset>
            <legend className="mb-3 text-sm font-medium">두 주인공</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2.5">
                <Label htmlFor="first-protagonist">첫 번째 주인공</Label>
                <Input
                  id="first-protagonist"
                  aria-describedby={
                    errors.protagonistNames ? "project-protagonists-error" : undefined
                  }
                  aria-invalid={errors.protagonistNames ? true : undefined}
                  value={draft.protagonistNames[0]}
                  onChange={(event) => updateField("firstProtagonist", event.target.value)}
                  required
                  disabled={isPending}
                  className="h-11 bg-background/60"
                />
              </div>
              <div className="space-y-2.5">
                <Label htmlFor="second-protagonist">두 번째 주인공</Label>
                <Input
                  id="second-protagonist"
                  aria-describedby={
                    errors.protagonistNames ? "project-protagonists-error" : undefined
                  }
                  aria-invalid={errors.protagonistNames ? true : undefined}
                  value={draft.protagonistNames[1]}
                  onChange={(event) => updateField("secondProtagonist", event.target.value)}
                  required
                  disabled={isPending}
                  className="h-11 bg-background/60"
                />
              </div>
            </div>
            {errors.protagonistNames && (
              <p
                id="project-protagonists-error"
                role="alert"
                className="mt-2 text-sm text-destructive"
              >
                {errors.protagonistNames}
              </p>
            )}
          </fieldset>

          {errors.form && (
            <p role="alert" className="text-sm text-destructive">
              {errors.form}
            </p>
          )}

          <Button
            type="submit"
            size="lg"
            disabled={isPending}
            className="h-11 w-full rounded-xl"
          >
            {isPending ? "작업 공간 여는 중" : "작업 공간 열기"}{" "}
            <ArrowRight data-icon="inline-end" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Export the feature and make the page a composition unit**

Add to `frontend/src/features/create-project/index.ts`:

```ts
export { ProjectSetupForm, type ProjectSetupFormProps } from "./ui/project-setup-form";
export {
  useProjectSetup,
  type ProjectSetupController,
  type UseProjectSetupOptions,
} from "./use-project-setup";
```

Refactor `frontend/src/pages/new-project/setup-page.tsx` so it imports no form event, React local-state hook, infrastructure type, infrastructure error, field primitive, or mutation hook. Keep the existing header, selected-trope card, and layout classes. Use this component boundary:

```tsx
import { Link, Navigate, useNavigate, useSearch } from "@tanstack/react-router";
import { ArrowLeft, Heart } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ProjectSetupForm, useProjectSetup } from "@/features/create-project";
import { TROPE_TEMPLATES, type TropeTemplate } from "@/modules/story-design";
import { BrandMark } from "@/shared/ui/brand-mark";

export function SetupPage() {
  const { trope: tropeId } = useSearch({ from: "/new_/setup" });
  const trope = TROPE_TEMPLATES.find(({ id }) => id === tropeId);

  if (!trope) {
    return <Navigate to="/new" replace />;
  }

  return <SetupPageContent key={trope.id} trope={trope} />;
}

function SetupPageContent({ trope }: { trope: TropeTemplate }) {
  const navigate = useNavigate({ from: "/new/setup" });
  const setup = useProjectSetup({
    tropeId: trope.id,
    starterLogline: trope.starterLogline,
    onCreated: (projectId) =>
      navigate({
        to: "/projects/$projectId/write",
        params: { projectId },
      }),
  });

  return (
    <div className="min-h-svh bg-background">
      <header className="border-b border-border/70">
        <div className="mx-auto flex h-18 max-w-6xl items-center justify-between px-6 lg:px-10">
          <BrandMark />
          <Button variant="ghost" asChild>
            <Link to="/new">
              <ArrowLeft data-icon="inline-start" />
              트로프 다시 선택
            </Link>
          </Button>
        </div>
      </header>
      <main className="mx-auto grid max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[0.8fr_1.2fr] lg:px-10 lg:py-16">
        <aside className="lg:pt-12">
          <p className="mb-4 text-xs font-semibold tracking-[0.22em] text-primary uppercase">
            New story · Step 2
          </p>
          <h1 className="font-heading text-4xl leading-tight font-semibold tracking-tight">
            이야기의 첫 문장을 준비할게요
          </h1>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            지금은 알고 있는 만큼만 적어도 충분해요. 나머지는 집필하면서 함께 발견할 수 있습니다.
          </p>
          <Card className="mt-8 border-primary/20 bg-secondary/55 shadow-none">
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-primary text-primary-foreground">
                  <Heart className="size-4" />
                </span>
                <div>
                  <p className="text-xs text-muted-foreground">선택한 트로프</p>
                  <p className="font-heading text-lg font-semibold">{trope.title}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {trope.tags.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </aside>

        <ProjectSetupForm setup={setup} />
      </main>
    </div>
  );
}
```

- [ ] **Step 6: Run focused setup and feature tests**

Run:

```sh
mise exec -- pnpm test --run src/features/create-project/project-setup-state.test.ts src/pages/new-project/setup-page.test.tsx
mise exec -- pnpm typecheck
```

Expected: all focused tests PASS and TypeScript exits 0. Confirm the page file contains no `ApiRequestError`, `CreateProjectRequest`, `useState`, `useReducer`, `useRef`, or non-`const` `as` assertion.

- [ ] **Step 7: Commit the feature-owned setup workflow**

```sh
git add frontend/src/features/create-project frontend/src/pages/new-project/setup-page.tsx frontend/src/pages/new-project/setup-page.test.tsx
git commit -m "refactor(frontend): move project setup workflow into feature"
```

Expected: focused tests remain green from the committed tree.

---

### Task 5: Enforce Page Boundaries with Rules, Oxlint, and an AST Test

**Files:**
- Modify: `frontend/docs/frontend-coding-rules.md`
- Create: `frontend/.oxlintrc.json`
- Create: `frontend/src/architecture/page-boundaries.test.ts`

**Interfaces:**
- Consumes: the final compliant setup page from Task 4 and the unchanged writing-workspace legacy source.
- Produces: lint diagnostics and `analyzePageSource(sourceText, fileName)` test coverage for infrastructure imports, restricted state hooks, and non-`const` assertions.

- [ ] **Step 1: Add the normative coding rules**

Update the owning sections of `frontend/docs/frontend-coding-rules.md` with the approved rule bodies. Include these exact enforceable statements:

```markdown
- Production files under `src/pages` must not import `src/app/infrastructure`.
  Transport requests, transport error classes, and contract-to-UI error
  conversion belong to feature or infrastructure adapters.
- Production page files must not own detailed presentation draft state through
  `useState`, `useReducer`, or `useRef`. Put that state in the feature or
  presentation unit that owns the interaction. TanStack Query and routing hooks
  used for page composition remain allowed.
- A type assertion is not a validation boundary. Production page files must not
  use non-`const` type assertions; narrow route, API, DOM, and other boundary
  values with an authoritative guard, parser, or adapter.
- Editing one field must not erase a server error for an unchanged field. Tie
  error visibility to the affected field or submitted-value snapshot instead
  of resetting the whole mutation from a generic field-change handler.
- Use a reducer only for explicit related transitions or a discriminated state
  machine that prevents impossible states. Do not replace independent setters
  mechanically or duplicate TanStack Query lifecycle state in a reducer.
- Every temporary page-boundary exception must name the file, enumerate the
  exact accepted violations and removal condition, and have an automated test
  that prevents its baseline from increasing.
```

Also add the approved form contract and accessibility rules:

```markdown
- HTML validation constraints and product guidance must agree with the owning
  domain contract and approved OpenAPI baseline. The frontend must not silently
  add a stricter business invariant; focused tests must cover each required or
  optional behavior enforced by the UI.
- Group related form controls semantically and expose asynchronously rendered
  validation feedback through an appropriate live-region or alert mechanism.
```

Document `src/pages/writing-workspace/writing-workspace-page.tsx` as the only temporary exception, its two infrastructure imports, four `useState` calls, four `useRef` calls, one non-`const` assertion, and full page extraction as the removal condition.

- [ ] **Step 2: Create the Oxlint page override**

Create `frontend/.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "overrides": [
    {
      "files": ["src/pages/**/*.ts", "src/pages/**/*.tsx"],
      "excludeFiles": [
        "src/pages/**/*.test.ts",
        "src/pages/**/*.test.tsx",
        "src/pages/writing-workspace/writing-workspace-page.tsx"
      ],
      "rules": {
        "no-restricted-imports": [
          "error",
          {
            "paths": [
              {
                "name": "react",
                "importNames": ["useState", "useReducer", "useRef"],
                "message": "Page files compose routes and features; move local interaction state to its feature or presentation owner."
              }
            ],
            "patterns": [
              {
                "group": ["@/app/infrastructure/**"],
                "message": "Page files must consume typed feature interfaces instead of infrastructure contracts or errors."
              }
            ]
          }
        ]
      }
    }
  ]
}
```

- [ ] **Step 3: Prove the lint configuration rejects a temporary violation**

Temporarily create `frontend/src/pages/page-boundary-lint-fixture.tsx` with:

```tsx
import { useState } from "react";

import type { CreateProjectRequest } from "@/app/infrastructure/api/contracts";

export function PageBoundaryLintFixture() {
  const [request] = useState<CreateProjectRequest | null>(null);
  return <p>{request?.title}</p>;
}
```

Run:

```sh
mise exec -- pnpm lint
```

Expected: FAIL with one restricted React import diagnostic and one restricted infrastructure import diagnostic for the fixture. Delete the fixture with `apply_patch` immediately after observing the failure; do not stage it.

- [ ] **Step 4: Write the AST analyzer and fixture tests**

Create `frontend/src/architecture/page-boundaries.test.ts`. Implement a TypeScript AST walk with this public test-local shape:

```ts
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";
import { describe, expect, test } from "vitest";

type ViolationKind = "infrastructure-import" | "state-hook" | "type-assertion";

interface PageBoundaryViolation {
  kind: ViolationKind;
  detail: string;
}

const restrictedHooks = new Set(["useState", "useReducer", "useRef"]);

export function analyzePageSource(
  sourceText: string,
  fileName: string,
): PageBoundaryViolation[] {
  const sourceFile = ts.createSourceFile(
    fileName,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const localHookNames = new Map<string, string>();
  const violations: PageBoundaryViolation[] = [];

  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) {
      continue;
    }

    const moduleName = statement.moduleSpecifier.text;
    if (moduleName.startsWith("@/app/infrastructure/")) {
      violations.push({ kind: "infrastructure-import", detail: moduleName });
    }

    if (moduleName !== "react") continue;
    const bindings = statement.importClause?.namedBindings;
    if (!bindings || !ts.isNamedImports(bindings)) continue;

    for (const element of bindings.elements) {
      const importedName = element.propertyName?.text ?? element.name.text;
      if (restrictedHooks.has(importedName)) {
        localHookNames.set(element.name.text, importedName);
      }
    }
  }

  function visit(node: ts.Node) {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
      const hook = localHookNames.get(node.expression.text);
      if (hook) violations.push({ kind: "state-hook", detail: hook });
    }

    if (ts.isTypeAssertionExpression(node)) {
      violations.push({ kind: "type-assertion", detail: "non-const" });
    }

    if (ts.isAsExpression(node)) {
      const suffix = sourceFile.text.slice(node.expression.end, node.end).trim();
      if (suffix !== "as const") {
        violations.push({ kind: "type-assertion", detail: "non-const" });
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return violations;
}
```

Add fixture tests that prove aliased hooks, infrastructure imports, and assertions are detected while `as const` is accepted:

```ts
describe("page boundary analyzer", () => {
  test("detects restricted imports, aliased state hooks, and unsafe assertions", () => {
    const violations = analyzePageSource(
      `
        import { useState as useLocalState } from "react";
        import type { ApiError } from "@/app/infrastructure/api/contracts";
        const value = "reunion" as ApiError;
        useLocalState(value);
      `,
      "fixture.tsx",
    );

    expect(summarize(violations)).toEqual({
      "infrastructure-import:@/app/infrastructure/api/contracts": 1,
      "state-hook:useState": 1,
      "type-assertion:non-const": 1,
    });
  });

  test("allows const assertions", () => {
    expect(analyzePageSource(`const values = ["one"] as const;`, "fixture.ts")).toEqual([]);
  });
});
```

Add these helpers and exact repository baseline in the same file:

```ts
const legacyBaseline: Record<string, Record<string, number>> = {
  "writing-workspace/writing-workspace-page.tsx": {
    "infrastructure-import:@/app/infrastructure/api/api-client": 1,
    "infrastructure-import:@/app/infrastructure/api/contracts": 1,
    "state-hook:useRef": 4,
    "state-hook:useState": 4,
    "type-assertion:non-const": 1,
  },
};

function summarize(violations: PageBoundaryViolation[]): Record<string, number> {
  return violations.reduce<Record<string, number>>((counts, violation) => {
    const key = `${violation.kind}:${violation.detail}`;
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});
}

function productionPageFiles(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return productionPageFiles(entryPath);
    if (!entry.isFile() || !/\.(ts|tsx)$/.test(entry.name) || /\.test\.(ts|tsx)$/.test(entry.name)) {
      return [];
    }
    return [entryPath];
  });
}

test("production pages match the zero-violation or frozen legacy baseline", () => {
  const pagesRoot = path.resolve(import.meta.dirname, "../pages");
  const files = productionPageFiles(pagesRoot);
  const observedLegacyFiles = new Set<string>();

  for (const file of files) {
    const relativePath = path.relative(pagesRoot, file).split(path.sep).join("/");
    const expected = legacyBaseline[relativePath] ?? {};
    if (legacyBaseline[relativePath]) observedLegacyFiles.add(relativePath);

    expect(
      summarize(analyzePageSource(fs.readFileSync(file, "utf8"), file)),
      relativePath,
    ).toEqual(expected);
  }

  expect([...observedLegacyFiles].sort()).toEqual(Object.keys(legacyBaseline).sort());
});
```

- [ ] **Step 5: Run architecture, lint, formatting, and type checks**

Run:

```sh
mise exec -- pnpm test --run src/architecture/page-boundaries.test.ts
mise exec -- pnpm format:check
mise exec -- pnpm lint
mise exec -- pnpm typecheck
```

Expected: analyzer fixture tests PASS, repository baseline test PASS, formatting is clean, Oxlint exits 0, and TypeScript exits 0. If formatting changes are needed, run `mise exec -- pnpm format`, inspect the diff, and rerun all four commands.

- [ ] **Step 6: Commit enforcement and documentation together**

```sh
git add frontend/.oxlintrc.json frontend/src/architecture/page-boundaries.test.ts frontend/docs/frontend-coding-rules.md
git commit -m "chore(frontend): enforce thin page boundaries"
```

Expected: the rule documentation and its automated enforcement are in the same commit.

---

### Task 6: Plan and Generate Project Setup E2E Coverage

**Files:**
- Create: `frontend/docs/e2e/project-setup-page-boundary-test-plan.md`
- Modify: `frontend/playwright.config.ts`
- Create: `frontend/project-setup-page-boundary.spec.ts`

**Interfaces:**
- Consumes: approved UI plan, approved OpenAPI baseline, completed setup implementation, and all component acceptance tests.
- Produces: deterministic browser coverage for optional logline creation and field-scoped error lifetime.

- [ ] **Step 1: Dispatch the required Playwright test planner**

Assign `.codex/agents/playwright_test_planner.toml` the affected route `/new/setup?trope=reunion`, approved UI-plan path and blob, OpenAPI operation `createProjectWorkspace` at blob `69d64146d62ab12b7462839a1f3ef0f76133374d`, and these two required scenarios:

```text
1. Create a project after clearing the prefilled logline; assert the POST body contains an empty logline and navigation uses the server-returned project id.
2. Receive simultaneous title and protagonist field errors; edit only the title; assert the title error disappears and the unchanged protagonist error remains associated with both inputs.
```

Require output at `frontend/docs/e2e/project-setup-page-boundary-test-plan.md`. Expected: planner edits no implementation or test file.

- [ ] **Step 2: Review and approve the E2E plan**

Confirm both scenarios are independent, start from `/new/setup?trope=reunion`, mock `POST /api/projects`, use role/label locators, and cover the exact expected URL and accessible feedback. Reject any visual redesign, extra product behavior, or unrelated route coverage.

- [ ] **Step 3: Configure deterministic Playwright startup**

Replace `frontend/playwright.config.ts` with:

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testMatch: "**/*.spec.ts",
  use: { baseURL: "http://127.0.0.1:4173" },
  webServer: {
    command: "VITE_ENABLE_MSW=false mise exec -- pnpm dev --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
  },
});
```

- [ ] **Step 4: Dispatch the required Playwright test generator**

Give `.codex/agents/playwright_test_generator.toml` the approved E2E plan and own only `frontend/project-setup-page-boundary.spec.ts`. Require this generated behavior and helper:

```ts
import { expect, test } from "@playwright/test";

test("creates a project with an empty logline", async ({ page }) => {
  let submittedBody: unknown;
  await page.route("**/api/projects", async (route) => {
    submittedBody = route.request().postDataJSON();
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(createWorkspace("e2e-empty-logline")),
    });
  });

  await page.goto("/new/setup?trope=reunion");
  await page.getByLabel("작품 제목").fill("빈 로그라인 이야기");
  await page.getByLabel("한 줄 아이디어").fill("");
  await page.getByRole("button", { name: "작업 공간 열기" }).click();

  await expect(page).toHaveURL(/\/projects\/e2e-empty-logline\/write$/);
  expect(submittedBody).toMatchObject({ logline: "" });
});

test("keeps the unchanged protagonist error after title editing", async ({ page }) => {
  await page.route("**/api/projects", (route) =>
    route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({
        code: "INVALID_PROTAGONISTS",
        message: "입력 내용을 확인해 주세요.",
        fieldErrors: [
          { path: "title", message: "이미 사용 중인 작품 제목이에요." },
          { path: "protagonistNames", message: "두 주인공의 이름을 확인해 주세요." },
        ],
      }),
    }),
  );

  await page.goto("/new/setup?trope=reunion");
  const title = page.getByLabel("작품 제목");
  await title.fill("겹치는 제목");
  await page.getByRole("button", { name: "작업 공간 열기" }).click();
  await expect(page.getByText("이미 사용 중인 작품 제목이에요.")).toBeVisible();

  await title.fill("새 제목");

  await expect(page.getByText("이미 사용 중인 작품 제목이에요.")).toBeHidden();
  await expect(page.getByText("두 주인공의 이름을 확인해 주세요.")).toBeVisible();
  await expect(page.getByLabel("첫 번째 주인공")).toHaveAccessibleDescription(
    "두 주인공의 이름을 확인해 주세요.",
  );
  await expect(page.getByLabel("두 번째 주인공")).toHaveAccessibleDescription(
    "두 주인공의 이름을 확인해 주세요.",
  );
});

function createWorkspace(projectId: string) {
  return {
    project: {
      id: projectId,
      title: "빈 로그라인 이야기",
      logline: "",
      tropeId: "reunion",
      updatedAt: "2026-07-20T00:00:00.000Z",
    },
    concept: {
      id: `${projectId}-concept`,
      projectId,
      tropeId: "reunion",
      logline: "",
      protagonistNames: ["서윤", "도현"],
    },
    storyBible: { projectId, characters: [], worldEntries: [] },
    manuscript: {
      id: `${projectId}-manuscript`,
      projectId,
      scenes: [
        {
          id: `${projectId}-scene-1`,
          title: "첫 장면",
          chapterNumber: 1,
          content: "",
          relatedCharacterIds: [],
          relatedWorldEntryIds: [],
        },
      ],
      activeSceneId: `${projectId}-scene-1`,
    },
    manuscriptRevision: 1,
  };
}
```

The generated file must not import application production code or modify product behavior.

- [ ] **Step 5: Run the generated browser tests**

Run:

```sh
mise exec -- pnpm exec playwright test project-setup-page-boundary.spec.ts
```

Expected: 2 tests PASS. Do not weaken assertions, skip tests, or add timing sleeps.

- [ ] **Step 6: Commit the E2E artifacts**

```sh
git add frontend/docs/e2e/project-setup-page-boundary-test-plan.md frontend/playwright.config.ts frontend/project-setup-page-boundary.spec.ts
git commit -m "test(frontend): cover project setup boundaries end to end"
```

Expected: the approved plan, deterministic runner config, and generated tests are committed together.

---

### Task 7: Run Read-Only Review, Resolve Findings, and Verify the Frontend

**Files:**
- Review boundary: all files changed by Tasks 1-6.
- Do not edit during the first review wave.

**Interfaces:**
- Consumes: completed frontend implementation, approved UI-plan blob, approved OpenAPI blob, design acceptance criteria, implementer handoff, and E2E results.
- Produces: triaged frontend review findings, any required repair commits, and final frontend verification evidence.

- [ ] **Step 1: Stop implementation editing and prepare the frontend handoff**

Record:

```text
Affected route: /new/setup
Entry point: frontend/src/pages/new-project/setup-page.tsx
Feature boundary: frontend/src/features/create-project/**
Architecture enforcement: frontend/.oxlintrc.json and frontend/src/architecture/page-boundaries.test.ts
API operation: createProjectWorkspace
Approved OpenAPI blob: 69d64146d62ab12b7462839a1f3ef0f76133374d
Relevant domains: docs/domains/projects.md and docs/domains/story-design.md
Accepted deviation: writing-workspace-page.tsx retains only its frozen documented baseline
UI plan: frontend/docs/ui-plans/project-setup-page-boundary.md plus its approved blob
E2E plan and test: frontend/docs/e2e/project-setup-page-boundary-test-plan.md and frontend/project-setup-page-boundary.spec.ts
```

Include changed files, commits, focused commands, and results. Confirm implementation agents have stopped editing.

- [ ] **Step 2: Dispatch the required read-only frontend review**

Assign `.codex/agents/frontend-review.toml` the complete affected setup screen and enforcement boundary with every handoff value above. Permit only read-only checks. Expected: evidence-based findings with IDs, severity, introduced/pre-existing classification, repair direction, and re-review requirement.

- [ ] **Step 3: Triage every finding**

For each finding, record one of:

```text
Accepted — repository evidence confirms the defect; return it to the frontend implementer.
Rejected — cite the exact design, domain, OpenAPI, UI-plan, or source evidence showing why it is not a defect.
Pre-existing — keep separate unless the change worsened it or it blocks affected correctness/safety.
```

Resolve every accepted finding regardless of severity. Re-dispatch the same reviewer for every Blocking/High repair and any repair that materially changes the reviewed behavior.

- [ ] **Step 4: Verify domain and contract alignment after repairs**

Run:

```sh
git hash-object docs/api/openapi.yaml
git hash-object docs/domains/projects.md
git hash-object docs/domains/story-design.md
```

Expected, in order:

```text
69d64146d62ab12b7462839a1f3ef0f76133374d
597be625750a5e9f0d43edb8453c57e42b3160b2
d2003bca7be68af9c4e35d87a9601252b7620bcd
```

- [ ] **Step 5: Run final focused and full verification**

Run from `frontend/`:

```sh
mise exec -- pnpm test --run src/modules/story-design/domain/story-concept.test.ts src/features/create-project/project-setup-state.test.ts src/architecture/page-boundaries.test.ts src/pages/new-project/setup-page.test.tsx
mise exec -- pnpm exec playwright test project-setup-page-boundary.spec.ts
mise exec -- pnpm check
mise exec -- pnpm build
```

Expected: every command exits 0; the Playwright run reports 2 passing tests; full Vitest reports no failing file; build completes successfully.

- [ ] **Step 6: Inspect final scope and commit any review repairs**

Run:

```sh
git status --short
git diff --check
git diff --name-only 1cc1b9d..HEAD
```

Expected: only design-approved frontend and documentation paths appear, `writing-workspace-page.tsx` is absent, and no unstaged repair remains. If repairs were needed, commit them with:

```sh
git commit -m "fix(frontend): resolve project setup review findings"
```

Before the commit, stage each accepted-finding repair path individually after matching it against the review triage; never stage unrelated files.

- [ ] **Step 7: Produce the final implementation handoff**

Report changed paths, behavior, rule enforcement, approved UI/OpenAPI baselines, E2E plan and generated test, reviewer findings and resolutions, domain-document non-change rationale, and every final command with its observed result. Do not claim completion if an accepted finding, required re-review, or verification command remains unresolved.
