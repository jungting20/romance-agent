import { expect, test, type Page } from "@playwright/test";

const ORIGIN = "http://127.0.0.1:4173";
const CHARACTERS_URL = `${ORIGIN}/projects/silver-garden/write?tab=characters`;

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

function snapshot(revision: number, characters: Array<typeof SEOYUN>): Record<string, unknown> {
  return {
    storyBibleRevision: revision,
    storyBible: { projectId: "silver-garden", characters, worldEntries: WORLD_ENTRIES },
  };
}

async function openCharacters(page: Page): Promise<void> {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto(CHARACTERS_URL);
  await expect(page.getByRole("heading", { name: "등장인물" })).toBeVisible();
}

async function interceptFetch(
  page: Page,
  method: "POST" | "PATCH",
  path: string,
  responses: Array<{ status: number; body: Record<string, unknown> }>,
): Promise<() => Promise<unknown[]>> {
  await page.evaluate(
    ({ method, path, responses }) => {
      const state = window as unknown as { requests: unknown[]; fetch: typeof fetch };
      state.requests = [];
      const fallback = window.fetch.bind(window);
      let index = 0;
      state.fetch = async (input, init) => {
        const request = new Request(input, init);
        if (request.method === method && new URL(request.url).pathname === path) {
          state.requests.push(await request.clone().json());
          const response = responses[Math.min(index++, responses.length - 1)];
          return new Response(JSON.stringify(response.body), {
            status: response.status,
            headers: { "Content-Type": "application/json" },
          });
        }
        return fallback(input, init);
      };
    },
    { method, path, responses },
  );
  return () => page.evaluate(() => (window as unknown as { requests: unknown[] }).requests);
}

test.describe("인물 카드 핵심 등록·수정", () => {
  test("desktop에서 모든 필드로 인물을 등록하고 서버 권위 snapshot만 반영한다", async ({
    page,
  }) => {
    // 1. 1280x800 새 context에서 characters 화면과 초기 두 주인공 action을 확인한다.
    await openCharacters(page);
    const createButton = page.getByRole("button", { name: "새 인물 등록" });
    await expect(createButton).toBeVisible();
    await expect(page.getByRole("button", { name: "서윤 인물 수정" })).toBeVisible();
    await expect(page.getByRole("button", { name: "도현 인물 수정" })).toBeVisible();

    const authoritativeMinseo = {
      ...SEOYUN,
      id: "server-character-3",
      name: "서버 민서",
      gender: "여성",
      age: "30세",
      role: "조력자",
      personality: "서버가 확정한 차분함",
      proseStyle: "서버 문체",
      dialogueStyle: "서버 대사",
      desire: "서버 욕망",
      hiddenFeeling: "서버 감정",
    };

    // 2. POST를 기록하고 완전한 권위 Story Bible snapshot을 201로 반환한다.
    const readPostBodies = await interceptFetch(
      page,
      "POST",
      "/api/projects/silver-garden/story-bible/characters",
      [{ status: 201, body: snapshot(2, [SEOYUN, DOHYEON, authoritativeMinseo]) }],
    );

    // 3. create Sheet의 focus와 필드 범위를 확인하고 9개 mutable 필드를 입력한다.
    await createButton.click();
    const dialog = page.getByRole("dialog", { name: "새 인물 등록" });
    const name = dialog.getByRole("textbox", { name: "이름 *" });
    await expect(name).toBeFocused();
    await expect(dialog.getByLabel("인물 ID")).toHaveCount(0);
    const values = {
      "이름 *": "민서",
      성별: "여성",
      나이: "스물아홉",
      역할: "서점 주인",
      성격: "차분하다.",
      문체: "짧은 문장",
      "대사 스타일": "정중한 말투",
      "기본 욕망": "서점을 지키고 싶다.",
      "숨은 감정": "다시 상처받을까 두렵다.",
    };
    for (const [label, value] of Object.entries(values)) {
      await dialog.getByRole("textbox", { name: label }).fill(value);
    }
    await expect(
      dialog.getByText(/삭제|충돌|덮어쓰기|이전 기억|현재 욕망|known|unknown|forbidden/i),
    ).toHaveCount(0);

    // 4. 저장하고 요청이 9개 mutable 문자열만 한 번 전송되는지 확인한다.
    await dialog.getByRole("button", { name: "저장" }).click();
    await expect(dialog).toBeHidden();
    const postBodies = await readPostBodies();
    expect(postBodies).toHaveLength(1);
    expect(postBodies[0]).toEqual({
      name: "민서",
      gender: "여성",
      age: "스물아홉",
      role: "서점 주인",
      personality: "차분하다.",
      proseStyle: "짧은 문장",
      dialogueStyle: "정중한 말투",
      desire: "서점을 지키고 싶다.",
      hiddenFeeling: "다시 상처받을까 두렵다.",
    });

    // 5. canonical URL, 권위 카드, 보존된 workspace, polite status와 focus 복귀를 확인한다.
    await expect(page).toHaveURL(CHARACTERS_URL);
    await expect(page.getByRole("button", { name: "서버 민서 인물 수정" })).toBeVisible();
    await expect(page.getByRole("button", { name: "서윤 인물 수정" })).toBeVisible();
    await expect(page.getByRole("button", { name: "도현 인물 수정" })).toBeVisible();
    await expect(page.getByText("서버 민서 인물을 저장했어요.")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    await expect(createButton).toBeFocused();
  });

  test("초기 주인공의 불변 ID를 유지하고 연속 수정의 마지막 서버 응답을 표시한다", async ({
    page,
  }) => {
    // 1. 주인공 direct URL을 열어 canonical URL, readonly ID와 seed 필드를 확인한다.
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(
      `${CHARACTERS_URL}&panel=character-editor&characterId=silver-garden-character-1`,
    );
    await expect(page).toHaveURL(
      `${CHARACTERS_URL}&panel=character-editor&characterId=silver-garden-character-1`,
    );
    let dialog = page.getByRole("dialog", { name: "서윤 수정" });
    const id = dialog.getByLabel("인물 ID");
    await expect(id).toHaveValue("silver-garden-character-1");
    await expect(id).toHaveAttribute("readonly", "");
    await expect(dialog.getByRole("textbox", { name: "이름 *" })).toHaveValue("서윤");
    for (const label of [
      "성별",
      "나이",
      "역할",
      "성격",
      "문체",
      "대사 스타일",
      "기본 욕망",
      "숨은 감정",
    ]) {
      await expect(dialog.getByRole("textbox", { name: label })).toBeVisible();
    }

    const responses = [
      { ...SEOYUN, name: "서버 서윤 1", hiddenFeeling: "서버 첫 감정" },
      { ...SEOYUN, name: "서버 서윤 2", hiddenFeeling: "서버 두 번째 감정" },
    ];

    // 2. PATCH 호출별 body를 기록하고 두 개의 완전한 권위 snapshot을 반환한다.
    const readPatchBodies = await interceptFetch(
      page,
      "PATCH",
      "/api/projects/silver-garden/story-bible/characters/silver-garden-character-1",
      responses.map((authoritative, index) => ({
        status: 200,
        body: snapshot(11 + index, [authoritative, DOHYEON]),
      })),
    );

    // 3. 이름과 숨은 감정만 바꾸는 저장을 두 번 수행하고 마지막 서버 값을 확인한다.
    await dialog.getByRole("textbox", { name: "이름 *" }).fill("로컬 서윤 1");
    await dialog.getByRole("textbox", { name: "숨은 감정" }).fill("로컬 첫 감정");
    await dialog.getByRole("button", { name: "저장" }).click();
    await expect(page.getByRole("button", { name: "서버 서윤 1 인물 수정" })).toBeVisible();
    await page.getByRole("button", { name: "서버 서윤 1 인물 수정" }).click();
    dialog = page.getByRole("dialog", { name: "서버 서윤 1 수정" });
    await dialog.getByRole("textbox", { name: "이름 *" }).fill("로컬 서윤 2");
    await dialog.getByRole("textbox", { name: "숨은 감정" }).fill("로컬 두 번째 감정");
    await dialog.getByRole("button", { name: "저장" }).click();
    await expect(page.getByRole("button", { name: "서버 서윤 2 인물 수정" })).toBeVisible();
    await expect(page.getByText(/숨은 감정 서버 두 번째 감정/)).toBeVisible();
    await expect(page.getByText(/서버 첫 감정/)).toHaveCount(0);

    // 4. 두 PATCH가 immutable path를 사용하고 변경 필드만 전송했는지 확인한다.
    expect(await readPatchBodies()).toEqual([
      { name: "로컬 서윤 1", hiddenFeeling: "로컬 첫 감정" },
      { name: "로컬 서윤 2", hiddenFeeling: "로컬 두 번째 감정" },
    ]);
    await expect(page.getByRole("button", { name: "도현 인물 수정" })).toBeVisible();
    await expect(page.getByText(/충돌|덮어쓰기|force-save|삭제/i)).toHaveCount(0);
  });

  test("trim 후 빈 이름을 product validation으로 막고 이름에 focus한다", async ({ page }) => {
    // 1. create Sheet에서 whitespace 이름을 저장하고 product validation과 zero POST를 확인한다.
    await openCharacters(page);
    let postCount = 0;
    await page.route("**/api/projects/silver-garden/story-bible/characters", async (route) => {
      if (route.request().method() === "POST") postCount += 1;
      await route.abort();
    });
    await page.getByRole("button", { name: "새 인물 등록" }).click();
    const dialog = page.getByRole("dialog", { name: "새 인물 등록" });
    const name = dialog.getByRole("textbox", { name: "이름 *" });
    await name.fill("   ");
    await dialog.getByRole("button", { name: "저장" }).click();
    await expect(dialog.getByRole("alert")).toContainText("이름을 입력해 주세요.");
    await expect(name).toHaveAttribute("aria-invalid", "true");
    await expect(name).toBeFocused();
    expect(postCount).toBe(0);

    // 2. 유효한 이름을 입력하면 이름 오류가 해제되고 선택 필드에 제약 오류가 생기지 않는다.
    await name.fill("민서");
    await expect(dialog.getByText("이름을 입력해 주세요.")).toHaveCount(0);
    await expect(name).toHaveAttribute("aria-invalid", "false");
    await expect(dialog.getByRole("alert")).toHaveCount(0);
  });
});
