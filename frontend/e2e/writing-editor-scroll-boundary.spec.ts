import { expect, test, type Locator, type Page } from "@playwright/test";

const ORIGIN = "http://127.0.0.1:4173";
const WRITE_PATH = "/projects/silver-garden/write";
const SCROLL_TARGET = 240;
const POSITION_TOLERANCE = 1;

const LONG_MANUSCRIPT = Array.from(
  { length: 180 },
  (_, index) =>
    `${String(index + 1).padStart(3, "0")}행 긴 원고 스크롤 경계를 검증하는 문장입니다.`,
).join("\n");

type EditorLayout = {
  editor: Locator;
  header: Locator;
  nav: Locator;
  textbox: Locator;
};

type ScrollMetrics = {
  documentScrollHeight: number;
  editorClientHeight: number;
  editorScrollHeight: number;
  editorScrollTop: number;
  headerTop: number;
  innerHeight: number;
  navTop: number;
  windowScrollY: number;
};

async function loadWorkspace(page: Page): Promise<Locator> {
  // 공통 시작 상태 2~3. 승인된 MSW seed 라우트로 이동하고 원고 editor가 로드될 때까지 기다린다.
  await page.goto(`${ORIGIN}${WRITE_PATH}`);

  const textbox = page.getByRole("textbox", { name: "원고 본문" });
  await expect(textbox).toBeVisible();

  return textbox;
}

async function prepareLongManuscript(page: Page, textbox: Locator): Promise<EditorLayout> {
  // 공통 시작 상태 4~5. 결정적인 180줄 원고를 입력하고 React 반영을 확인한다.
  await textbox.fill(LONG_MANUSCRIPT);
  await expect(textbox).toHaveValue(LONG_MANUSCRIPT);

  // 공통 시작 상태 6. 원고 textbox에서 가장 가까운 main과 tablist에서 가장 가까운 nav를 찾는다.
  const editor = textbox.locator("xpath=ancestor::main[1]");
  const header = page.locator("header").first();
  const nav = page.getByRole("tablist", { name: "집필 도메인" }).locator("xpath=ancestor::nav[1]");

  await expect(editor).toBeVisible();
  await expect(header).toBeVisible();
  await expect(nav).toBeVisible();

  // 공통 시작 상태 7. 중앙 main의 실제 overflow가 생길 때까지 레이아웃 계산을 기다린다.
  await expect
    .poll(async () => editor.evaluate((element) => element.scrollHeight > element.clientHeight))
    .toBe(true);

  return { editor, header, nav, textbox };
}

async function readScrollMetrics(editor: Locator): Promise<ScrollMetrics> {
  return editor.evaluate((element) => {
    const header = document.querySelector("header");
    const nav = document
      .querySelector('[role="tablist"][aria-label="집필 도메인"]')
      ?.closest("nav");

    if (!(header instanceof HTMLElement) || !(nav instanceof HTMLElement)) {
      throw new Error("집필 workspace의 header 또는 nav를 찾을 수 없습니다.");
    }

    return {
      documentScrollHeight: document.documentElement.scrollHeight,
      editorClientHeight: element.clientHeight,
      editorScrollHeight: element.scrollHeight,
      editorScrollTop: element.scrollTop,
      headerTop: header.getBoundingClientRect().top,
      innerHeight: window.innerHeight,
      navTop: nav.getBoundingClientRect().top,
      windowScrollY: window.scrollY,
    };
  });
}

async function verifyScrollBoundary(editor: Locator): Promise<void> {
  // 공통 스크롤 검증 2~3. 문서, editor, header, nav 초기 수치를 한 번에 읽고 경계를 확인한다.
  const before = await readScrollMetrics(editor);

  expect(before.documentScrollHeight).toBeLessThanOrEqual(before.innerHeight);
  expect(before.windowScrollY).toBe(0);
  expect(before.editorScrollHeight).toBeGreaterThan(before.editorClientHeight);
  expect(Math.abs(before.headerTop)).toBeLessThanOrEqual(POSITION_TOLERANCE);
  expect(Math.abs(before.navTop - 64)).toBeLessThanOrEqual(POSITION_TOLERANCE);

  // 공통 스크롤 검증 4. 중앙 editor만 240px 스크롤하고 실제 목표값 도달을 기다린다.
  await editor.evaluate((element, scrollTarget) => {
    element.scrollTop = scrollTarget;
  }, SCROLL_TARGET);

  await expect.poll(async () => editor.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await expect
    .poll(async () =>
      editor.evaluate(
        (element, scrollTarget) => Math.abs(element.scrollTop - scrollTarget),
        SCROLL_TARGET,
      ),
    )
    .toBeLessThanOrEqual(POSITION_TOLERANCE);

  // 공통 스크롤 검증 5. editor 스크롤 뒤에도 문서와 고정 영역 위치가 유지되는지 확인한다.
  const after = await readScrollMetrics(editor);

  expect(after.documentScrollHeight).toBeLessThanOrEqual(after.innerHeight);
  expect(after.windowScrollY).toBe(0);
  expect(Math.abs(after.headerTop - before.headerTop)).toBeLessThanOrEqual(POSITION_TOLERANCE);
  expect(Math.abs(after.navTop - before.navTop)).toBeLessThanOrEqual(POSITION_TOLERANCE);
}

test.describe("집필 에디터 스크롤 경계", () => {
  test("375x500 모바일에서 중앙 스크롤과 문맥 Sheet를 보존한다", async ({ page }) => {
    // 1. 375x500 viewport에서 공통 긴 원고 준비와 스크롤 경계 검증을 수행한다.
    await page.setViewportSize({ width: 375, height: 500 });
    const textbox = await loadWorkspace(page);
    const { editor } = await prepareLongManuscript(page, textbox);
    await verifyScrollBoundary(editor);

    // 2. 인물 보기 탭을 클릭한다.
    await page.getByRole("tab", { name: "인물 보기" }).click();

    // 3. 모바일 문맥 Sheet와 등장인물 콘텐츠가 보이는지 확인한다.
    const dialog = page.getByRole("dialog", { name: "인물 보기" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("등장인물", { exact: true })).toBeVisible();

    // 4. Sheet를 닫고 dialog가 사라지는지 확인한다.
    await page.getByRole("button", { name: "닫기" }).click();
    await expect(dialog).toBeHidden();

    // 5. Sheet 종료 뒤에도 원고 editor가 보이는지 확인한다.
    await expect(textbox).toBeVisible();
  });

  test("1024x500 고정 패널에서 중앙 스크롤 경계를 유지한다", async ({ page }) => {
    // 1. 1024x500 viewport에서 원고 editor와 inline 원고 목차를 확인한다.
    await page.setViewportSize({ width: 1024, height: 500 });
    const textbox = await loadWorkspace(page);
    const outlineHeading = page.getByRole("heading", { name: "원고 목차" });
    await expect(outlineHeading).toBeVisible();

    // 2. 고정 패널 너비에는 resize separator가 없는지 확인한다.
    await expect(page.getByRole("separator")).toHaveCount(0);

    // 3. 공통 긴 원고 준비와 스크롤 경계 검증을 수행한다.
    const { editor } = await prepareLongManuscript(page, textbox);
    await verifyScrollBoundary(editor);

    // 4. 검증 뒤에도 inline 원고 목차가 보이고 dialog가 열리지 않았는지 확인한다.
    await expect(outlineHeading).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("1440x500 리사이즈 패널에서 중앙 스크롤 경계를 유지한다", async ({ page }) => {
    // 1. 1440x500 viewport에서 원고 editor와 inline 원고 목차를 확인한다.
    await page.setViewportSize({ width: 1440, height: 500 });
    const textbox = await loadWorkspace(page);
    await expect(page.getByRole("heading", { name: "원고 목차" })).toBeVisible();

    // 2. 초기 리사이즈 패널 separator가 정확히 1개인지 확인한다.
    await expect(page.getByRole("separator")).toHaveCount(1);

    // 3. 공통 긴 원고 준비와 스크롤 경계 검증을 수행한다.
    const { editor } = await prepareLongManuscript(page, textbox);
    await verifyScrollBoundary(editor);

    // 4. AI 도구를 열고 넓은 화면의 세 번째 inline 패널 분기를 확인한다.
    await page.getByRole("button", { name: "AI 도구 열기" }).click();
    await expect(page.getByRole("dialog", { name: "AI 집필 도구" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "AI 집필 도구" })).toBeVisible();
    await expect(page.getByRole("separator")).toHaveCount(2);
  });
});
