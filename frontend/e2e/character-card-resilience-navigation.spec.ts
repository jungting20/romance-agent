import { expect, test, type Locator, type Page } from "@playwright/test";

const ORIGIN = "http://127.0.0.1:4173";
const CHARACTERS_URL = `${ORIGIN}/projects/silver-garden/write?tab=characters`;
const EDITOR_URL = `${CHARACTERS_URL}&panel=character-editor&characterId=silver-garden-character-1`;

const SEOYUN = {
  id: "silver-garden-character-1",
  name: "서윤",
  gender: "여성",
  age: "31세",
  role: "protagonist",
  personality: "단호하고 세심하다.",
  proseStyle: "감각적인 묘사와 짧은 문장을 쓴다.",
  dialogueStyle: "감정을 숨기며 간결하게 말한다.",
  desire: "상대에게 흔들리지 않고 자신의 선택을 지키고 싶다.",
  hiddenFeeling: "여전히 상대의 진심을 확인하고 싶다.",
};
const DOHYEON = {
  id: "silver-garden-character-2",
  name: "도현",
  gender: "남성",
  age: "33세",
  role: "protagonist",
  personality: "침착하고 주의 깊다.",
  proseStyle: "절제된 문장으로 움직임을 묘사한다.",
  dialogueStyle: "직접적이지만 말끝을 흐린다.",
  desire: "과거의 오해를 풀고 다시 신뢰받고 싶다.",
  hiddenFeeling: "이번에는 먼저 놓치고 싶지 않다.",
};
const WORLD_ENTRIES = [
  {
    id: "silver-garden-world-1",
    kind: "place",
    title: "비가 그친 온실",
    description: "두 사람이 과거에 마지막으로 만났던 장소. 젖은 흙과 오래된 장미 향이 남아 있다.",
  },
];

function snapshot(character = SEOYUN): Record<string, unknown> {
  return {
    storyBibleRevision: 2,
    storyBible: {
      projectId: "silver-garden",
      characters: [character, DOHYEON],
      worldEntries: WORLD_ENTRIES,
    },
  };
}

async function openEditor(page: Page): Promise<Locator> {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(EDITOR_URL);
  const dialog = page.getByRole("dialog", { name: "서윤 수정" });
  await expect(dialog).toBeVisible();
  return dialog;
}

async function openEditorFromLaunch(page: Page): Promise<Locator> {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(CHARACTERS_URL);
  await page.getByRole("button", { name: "서윤 인물 수정" }).click();
  const dialog = page.getByRole("dialog", { name: "서윤 수정" });
  await expect(dialog).toBeVisible();
  return dialog;
}

async function interceptFetch(
  page: Page,
  method: "PATCH" | "PUT",
  pathPrefix: string,
  responses: Array<{ status: number; body: Record<string, unknown>; delay?: number }>,
): Promise<() => Promise<unknown[]>> {
  await page.evaluate(
    ({ method, pathPrefix, responses }) => {
      const state = window as unknown as { requests: unknown[]; fetch: typeof fetch };
      state.requests = [];
      const fallback = window.fetch.bind(window);
      let index = 0;
      state.fetch = async (input, init) => {
        const request = new Request(input, init);
        if (request.method === method && new URL(request.url).pathname.startsWith(pathPrefix)) {
          state.requests.push(await request.clone().json());
          const response = responses[Math.min(index++, responses.length - 1)];
          if (response.delay) await new Promise((resolve) => setTimeout(resolve, response.delay));
          return new Response(JSON.stringify(response.body), {
            status: response.status,
            headers: { "Content-Type": "application/json" },
          });
        }
        return fallback(input, init);
      };
    },
    { method, pathPrefix, responses },
  );
  return () => page.evaluate(() => (window as unknown as { requests: unknown[] }).requests);
}

async function installArmedManuscriptFailure(page: Page): Promise<{
  arm: () => Promise<void>;
  readRequests: () => Promise<unknown[]>;
}> {
  await page.evaluate(() => {
    const state = window as unknown as {
      manuscriptRequests: unknown[];
      releaseManuscriptFailure?: () => void;
      fetch: typeof fetch;
    };
    state.manuscriptRequests = [];
    const fallback = window.fetch.bind(window);
    let release: (() => void) | undefined;
    const armed = new Promise<void>((resolve) => {
      release = resolve;
    });
    state.releaseManuscriptFailure = release;
    state.fetch = async (input, init) => {
      const request = new Request(input, init);
      if (
        request.method === "PUT" &&
        new URL(request.url).pathname.startsWith("/api/manuscripts/")
      ) {
        state.manuscriptRequests.push(await request.clone().json());
        await armed;
        return new Response(
          JSON.stringify({ code: "INTERNAL_ERROR", message: "실패", fieldErrors: [] }),
          { status: 500, headers: { "Content-Type": "application/json" } },
        );
      }
      return fallback(input, init);
    };
  });
  return {
    arm: () =>
      page.evaluate(() => {
        (
          window as unknown as { releaseManuscriptFailure?: () => void }
        ).releaseManuscriptFailure?.();
      }),
    readRequests: () =>
      page.evaluate(
        () => (window as unknown as { manuscriptRequests: unknown[] }).manuscriptRequests,
      ),
  };
}

test.describe("저장 실패·이탈·history 복원력", () => {
  test("500 저장 실패에서 exact draft를 보존하고 한 번만 재시도한다", async ({ page }) => {
    // 1. 서윤 편집기를 열고 첫 PATCH는 지연된 500, 둘째 PATCH는 권위 snapshot으로 응답한다.
    const dialog = await openEditor(page);
    const readBodies = await interceptFetch(
      page,
      "PATCH",
      "/api/projects/silver-garden/story-bible/characters/silver-garden-character-1",
      [
        {
          status: 500,
          delay: 150,
          body: { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
        },
        { status: 200, body: snapshot({ ...SEOYUN, hiddenFeeling: "서버가 확정한 재시도 감정" }) },
      ],
    );

    // 2. exact draft를 저장하며 빠른 두 번째 클릭을 시도하고 실패 상태·disabled·단일 요청을 확인한다.
    const feeling = dialog.getByRole("textbox", { name: "숨은 감정" });
    await feeling.fill("실패 뒤에도 남는 초안");
    const save = dialog.getByRole("button", { name: "저장" });
    await save.click();
    await expect(dialog.getByRole("button", { name: "저장 중…" })).toBeDisabled();
    await save.click({ force: true });
    await expect(dialog.getByRole("alert")).toContainText("입력한 내용은 그대로 유지했어요");
    await expect(feeling).toHaveValue("실패 뒤에도 남는 초안");
    await expect(dialog.getByLabel("인물 ID")).toHaveValue("silver-garden-character-1");
    await expect(dialog.getByRole("button", { name: "다시 저장" })).toBeVisible();
    expect(await readBodies()).toHaveLength(1);

    // 3. 다시 저장을 한 번 실행하고 두 요청의 동일 draft와 권위 카드·status를 확인한다.
    await dialog.getByRole("button", { name: "다시 저장" }).click();
    await expect(dialog).toBeHidden();
    expect(await readBodies()).toEqual([
      { hiddenFeeling: "실패 뒤에도 남는 초안" },
      { hiddenFeeling: "실패 뒤에도 남는 초안" },
    ]);
    await expect(page.getByText(/숨은 감정 서버가 확정한 재시도 감정/)).toBeVisible();
    await expect(page.getByText("서윤 인물을 저장했어요.")).toHaveAttribute("aria-live", "polite");
  });

  test("PATCH 404를 unavailable 상태로 전환하고 draft를 보존한다", async ({ page }) => {
    // 1. PATCH 404 뒤 unavailable 안내, exact draft, readonly ID와 disabled controls를 확인한다.
    const dialog = await openEditor(page);
    await interceptFetch(
      page,
      "PATCH",
      "/api/projects/silver-garden/story-bible/characters/silver-garden-character-1",
      [
        {
          status: 404,
          body: {
            code: "CHARACTER_NOT_FOUND",
            message: "인물을 찾을 수 없습니다.",
            fieldErrors: [],
          },
        },
      ],
    );
    const feeling = dialog.getByRole("textbox", { name: "숨은 감정" });
    await feeling.fill("404 뒤에도 남는 초안");
    await dialog.getByRole("button", { name: "저장" }).click();
    await expect(dialog.getByRole("alert")).toContainText("이 인물을 더 이상 편집할 수 없어요.");
    await expect(dialog.getByRole("alert")).toContainText("등장인물 목록으로 돌아가");
    await expect(feeling).toHaveValue("404 뒤에도 남는 초안");
    await expect(dialog.getByLabel("인물 ID")).toHaveValue("silver-garden-character-1");
    for (const label of [
      "이름 *",
      "성별",
      "나이",
      "역할",
      "성격",
      "문체",
      "대사 스타일",
      "기본 욕망",
      "숨은 감정",
    ]) {
      await expect(dialog.getByRole("textbox", { name: label })).toBeDisabled();
    }
    await expect(dialog.getByRole("button", { name: "다시 저장" })).toBeDisabled();
    await expect(dialog.getByText(/충돌|병합|덮어쓰기|force-save/i)).toHaveCount(0);

    // 2. 등장인물 목록으로 돌아간 뒤 discard를 한 번 확정하고 canonical URL과 seed 카드를 확인한다.
    await dialog.getByRole("button", { name: "등장인물 목록으로 돌아가기" }).click();
    await page
      .getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" })
      .getByRole("button", { name: "변경사항 버리기" })
      .click();
    await expect(dialog).toBeHidden();
    await expect(page).toHaveURL(CHARACTERS_URL);
    await expect(page.getByRole("button", { name: "서윤 인물 수정" })).toBeVisible();
    await expect(page.getByRole("button", { name: "도현 인물 수정" })).toBeVisible();
  });

  for (const closeMethod of ["명시적 닫기", "Escape", "overlay"] as const) {
    test(`dirty ${closeMethod}가 단 한 번의 discard 확인을 거친다`, async ({ page }) => {
      // 1. 독립 context에서 서윤 편집기를 dirty로 만들고 지정된 close method를 수행한다.
      const dialog = await openEditorFromLaunch(page);
      const personality = dialog.getByRole("textbox", { name: "성격" });
      const draft = `단호하고 세심하다. ${closeMethod} 초안`;
      await personality.fill(draft);
      const close = async () => {
        if (closeMethod === "명시적 닫기")
          await dialog.getByRole("button", { name: "인물 편집기 닫기" }).click();
        else if (closeMethod === "Escape") await page.keyboard.press("Escape");
        else
          await page
            .locator('[data-slot="sheet-overlay"]')
            .last()
            .click({ position: { x: 2, y: 2 }, force: true });
      };
      await close();

      // 2. 계속 편집을 선택해 URL, exact draft와 editor focus context를 보존한다.
      const discard = page.getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" });
      await discard.getByRole("button", { name: "계속 편집" }).click();
      await expect(dialog).toBeVisible();
      await expect(page).toHaveURL(EDITOR_URL);
      await expect(personality).toHaveValue(draft);
      await expect(dialog.locator(":focus")).toHaveCount(1);

      // 3. 같은 method 뒤 변경사항 버리기를 한 번 선택해 두 dialog와 stale draft를 제거한다.
      await close();
      await page
        .getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" })
        .getByRole("button", { name: "변경사항 버리기" })
        .click();
      await expect(dialog).toBeHidden();
      await expect(discard).toBeHidden();
      await expect(page).toHaveURL(CHARACTERS_URL);
      await expect(page.getByRole("button", { name: "서윤 인물 수정" })).toBeFocused();
    });
  }

  test("clean Back·Forward를 재생하고 dirty Back은 확인 전까지 막는다", async ({ page }) => {
    // 1. 목록에서 clean Sheet를 연 뒤 Back/Forward로 동일 editor와 seed draft를 복원한다.
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(CHARACTERS_URL);
    await page.getByRole("button", { name: "서윤 인물 수정" }).click();
    let dialog = page.getByRole("dialog", { name: "서윤 수정" });
    await page.goBack();
    await expect(dialog).toBeHidden();
    await expect(page).toHaveURL(CHARACTERS_URL);
    await page.goForward();
    dialog = page.getByRole("dialog", { name: "서윤 수정" });
    await expect(dialog.getByRole("textbox", { name: "성격" })).toHaveValue(SEOYUN.personality);

    // 2. dirty Back 뒤 계속 편집을 선택해 editor URL과 exact draft를 유지한다.
    const personality = dialog.getByRole("textbox", { name: "성격" });
    const draft = `${SEOYUN.personality} history 초안`;
    await personality.fill(draft);
    await page.goBack();
    await page
      .getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" })
      .getByRole("button", { name: "계속 편집" })
      .click();
    await expect(page).toHaveURL(EDITOR_URL);
    await expect(personality).toHaveValue(draft);
    await expect(dialog.locator(":focus")).toHaveCount(1);

    // 3. 다시 Back하고 discard를 확정해 목록으로 한 번만 이동한다.
    await page.goBack();
    await page
      .getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" })
      .getByRole("button", { name: "변경사항 버리기" })
      .click();
    await expect(page).toHaveURL(CHARACTERS_URL);
    await expect(dialog).toBeHidden();
    await expect(
      page.getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" }),
    ).toHaveCount(0);
  });

  test("confirmed route 이탈 뒤 manuscript flush가 실패하면 character draft를 복원한다", async ({
    page,
  }) => {
    // 1. 목록에서 UI로 editor를 열어 history를 만든 뒤 원고와 character를 dirty로 하고 PUT 실패를 준비한다.
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(CHARACTERS_URL);
    await page.getByRole("button", { name: "서윤 인물 수정" }).click();
    const dialog = page.getByRole("dialog", { name: "서윤 수정" });
    await expect(dialog).toBeVisible();
    const manuscriptFailure = await installArmedManuscriptFailure(page);
    await page.locator('[aria-label="원고 본문"]').evaluate((element, value) => {
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
      setter?.call(element, value);
      element.dispatchEvent(new Event("input", { bubbles: true }));
      element.dispatchEvent(new Event("change", { bubbles: true }));
    }, "탐색 전에 실패할 원고");
    const personality = dialog.getByRole("textbox", { name: "성격" });
    const draft = `${SEOYUN.personality} 탐색 실패 뒤에도 남는 인물 초안`;
    await personality.fill(draft);
    // 2. Back 탐색의 character discard를 확정하고 flush 실패 뒤 동일 character draft와 URL 복원을 확인한다.
    await page.goBack();
    const confirmDiscard = page
      .getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" })
      .getByRole("button", { name: "변경사항 버리기" })
      .click();
    await manuscriptFailure.arm();
    await confirmDiscard;
    await expect.poll(manuscriptFailure.readRequests).toHaveLength(1);
    await expect(page.getByText("저장 실패")).toBeVisible();
    await expect(page).toHaveURL(EDITOR_URL);
    await expect(page.getByRole("dialog", { name: "서윤 수정" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "성격" })).toHaveValue(draft);
  });
});

test.describe("모바일 중첩 Sheet와 focus", () => {
  test("375px Context Sheet 위에서 character Sheet를 열고 닫아 focus를 복원한다", async ({
    page,
  }) => {
    // 1. 375x800 기본 workspace에서 인물 보기 Context Sheet와 character actions를 확인한다.
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto(`${ORIGIN}/projects/silver-garden/write`);
    await page.getByRole("tab", { name: "인물 보기" }).click();
    const contextDialog = page.getByRole("dialog", { name: "인물 보기" });
    await expect(contextDialog.getByRole("heading", { name: "등장인물" })).toBeVisible();
    await expect(contextDialog.getByRole("button", { name: "새 인물 등록" })).toBeVisible();
    const editLaunch = contextDialog.getByRole("button", { name: "서윤 인물 수정" });
    await expect(editLaunch).toBeVisible();
    await expect(contextDialog.getByRole("button", { name: "도현 인물 수정" })).toBeVisible();

    // 2. edit Sheet를 Context 위에 열어 두 sheet-content, 초기 focus, readonly ID와 scroll lock을 확인한다.
    await editLaunch.click();
    const editDialog = page.getByRole("dialog", { name: "서윤 수정" });
    await expect(editDialog.getByRole("textbox", { name: "이름 *" })).toBeFocused();
    await expect(editDialog.getByLabel("인물 ID")).toHaveAttribute("readonly", "");
    await expect(page.locator('[data-slot="sheet-content"]')).toHaveCount(2);
    await expect(page.locator("body")).toHaveCSS("overflow", "hidden");

    // 3. Tab 양방향 focus가 top Sheet에 갇히는지 확인하고 clean 취소 뒤 launch focus를 복원한다.
    for (let index = 0; index < 14; index += 1) {
      await page.keyboard.press("Tab");
      await expect(editDialog.locator(":focus")).toHaveCount(1);
    }
    await page.keyboard.press("Shift+Tab");
    await expect(editDialog.locator(":focus")).toHaveCount(1);
    await editDialog.getByRole("button", { name: "취소" }).click();
    await expect(editDialog).toBeHidden();
    await expect(contextDialog).toBeVisible();
    await expect(editLaunch).toBeFocused();

    // 4. dirty create Escape에서 계속 편집과 discard를 거쳐 Context와 launch focus를 복원한다.
    const createLaunch = contextDialog.getByRole("button", { name: "새 인물 등록" });
    await createLaunch.click();
    const createDialog = page.getByRole("dialog", { name: "새 인물 등록" });
    const name = createDialog.getByRole("textbox", { name: "이름 *" });
    await name.fill("모바일 민서");
    await page.keyboard.press("Escape");
    let discard = page.getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" });
    await expect(discard.getByRole("button", { name: "계속 편집" })).toBeFocused();
    await discard.getByRole("button", { name: "계속 편집" }).click();
    await expect(name).toHaveValue("모바일 민서");
    await expect(createDialog.locator(":focus")).toHaveCount(1);
    await page.keyboard.press("Escape");
    discard = page.getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" });
    await discard.getByRole("button", { name: "변경사항 버리기" }).click();
    await expect(createDialog).toBeHidden();
    await expect(contextDialog).toBeVisible();
    await expect(createLaunch).toBeFocused();
  });
});
