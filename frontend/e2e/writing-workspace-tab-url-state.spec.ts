import { expect, test, type Page } from "@playwright/test";

const ORIGIN = "http://127.0.0.1:4173";
const WRITE_PATH = "/projects/silver-garden/write";

type ContextExpectation = {
  heading: string;
  label: string;
  search: string;
};

const contexts: ContextExpectation[] = [
  { heading: "원고 목차", label: "원고 보기", search: "" },
  { heading: "등장인물", label: "인물 보기", search: "?tab=characters" },
  { heading: "세계관", label: "세계관 보기", search: "?tab=world" },
];

async function loadWorkspace(page: Page): Promise<void> {
  await page.goto(`${ORIGIN}${WRITE_PATH}`);
  await expect(page.getByRole("textbox", { name: "원고 본문" })).toBeVisible();
}

async function expectSelectedContext(
  page: Page,
  context: ContextExpectation,
  inline: boolean,
): Promise<void> {
  await expect(page.getByRole("tab", { name: context.label })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page).toHaveURL(`${ORIGIN}${WRITE_PATH}${context.search}`);

  if (inline) {
    await expect(page.getByRole("heading", { name: context.heading, exact: true })).toBeVisible();
    for (const inactiveContext of contexts.filter(({ label }) => label !== context.label)) {
      await expect(
        page.getByRole("heading", { name: inactiveContext.heading, exact: true }),
      ).toHaveCount(0);
    }
  }
}

for (const viewport of [
  { height: 800, width: 375 },
  { height: 800, width: 768 },
  { height: 800, width: 1440 },
]) {
  test(`${viewport.width}x${viewport.height}에서 세로 문맥 탭 방향키와 URL을 동기화한다`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const consoleErrors: string[] = [];
    const networkErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("response", (response) => {
      if (response.status() >= 400) {
        networkErrors.push(`${response.status().toString()} ${response.url()}`);
      }
    });

    await loadWorkspace(page);

    const tablist = page.getByRole("tablist", { name: "집필 도메인" });
    const manuscriptTab = page.getByRole("tab", { name: "원고 보기" });
    const charactersTab = page.getByRole("tab", { name: "인물 보기" });
    const worldTab = page.getByRole("tab", { name: "세계관 보기" });
    const inline = viewport.width >= 768;

    await expect(tablist).toHaveAttribute("aria-orientation", "vertical");
    await manuscriptTab.focus();
    await page.keyboard.press("ArrowDown");
    await expectSelectedContext(page, contexts[1], inline);
    await expect(charactersTab).toBeFocused();

    await page.keyboard.press("ArrowDown");
    await expectSelectedContext(page, contexts[2], inline);
    await expect(worldTab).toBeFocused();

    await page.keyboard.press("ArrowDown");
    await expectSelectedContext(page, contexts[0], inline);
    await expect(manuscriptTab).toBeFocused();

    await page.keyboard.press("ArrowUp");
    await expectSelectedContext(page, contexts[2], inline);
    await expect(worldTab).toBeFocused();

    await page.goBack();
    await expectSelectedContext(page, contexts[0], inline);
    await page.goForward();
    await expectSelectedContext(page, contexts[2], inline);

    if (!inline) {
      await worldTab.click();
      const sheet = page.getByRole("dialog", { name: "세계관 보기" });
      await expect(sheet).toBeVisible();
      await expect(sheet.getByRole("heading", { name: "세계관", exact: true })).toBeVisible();
      await page.getByRole("button", { name: "닫기" }).click();
      await expect(sheet).toBeHidden();
      await expectSelectedContext(page, contexts[2], false);
    }

    expect(consoleErrors).toEqual([]);
    expect(networkErrors).toEqual([]);
  });
}

test("direct URL과 invalid/manuscript canonicalization을 보존한다", async ({ page }) => {
  await page.setViewportSize({ height: 800, width: 768 });

  await page.goto(`${ORIGIN}${WRITE_PATH}?tab=characters`);
  await expect(page.getByRole("textbox", { name: "원고 본문" })).toBeVisible();
  await expectSelectedContext(page, contexts[1], true);

  await page.goto(`${ORIGIN}${WRITE_PATH}?tab=manuscript&view=dense`);
  await expectSelectedContext(page, { ...contexts[0], search: "?view=dense" }, true);

  await page.goto(`${ORIGIN}${WRITE_PATH}?tab=unsupported&view=dense`);
  await expectSelectedContext(page, { ...contexts[0], search: "?view=dense" }, true);
});
