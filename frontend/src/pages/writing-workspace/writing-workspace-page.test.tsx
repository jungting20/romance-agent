import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserHistory, RouterProvider } from "@tanstack/react-router";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, test, vi } from "vitest";

import type {
  CompareManuscriptSceneResponse,
  ProjectWorkspaceResponse,
  SaveManuscriptRequest,
  SaveManuscriptResponse,
  SaveWorldEntriesRequest,
  StoryBibleSnapshot,
} from "@/app/infrastructure/api/contracts";
import { createAppMemoryRouter, createAppRouter } from "@/app/app";
import { findMockWorkspace } from "@/mocks/data/project-workspaces";
import { server } from "@/mocks/server";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function setViewportWidth(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => {
    const minimumWidth = Number(query.match(/min-width:\s*(\d+)px/)?.[1] ?? 0);
    return {
      matches: width >= minimumWidth,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    } satisfies MediaQueryList;
  });
}

describe("WritingWorkspacePage", () => {
  test("shows a workspace skeleton while the workspace is being fetched", async () => {
    server.use(
      http.get("/api/projects/:projectId/workspace", async () => {
        await delay("infinite");
        return HttpResponse.json({});
      }),
    );

    const { container } = renderWorkspace();

    const loadingWorkspace = await screen.findByRole("status");

    expect(loadingWorkspace).toHaveTextContent("작업 공간을 불러오는 중이에요.");
    expect(loadingWorkspace).toHaveClass("h-svh", "min-h-0", "overflow-hidden");
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(3);
  });

  test("retries a transient workspace loading error", async () => {
    let requestCount = 0;
    const workspace = getWorkspace();
    server.use(
      http.get("/api/projects/:projectId/workspace", () => {
        requestCount += 1;
        return requestCount === 1
          ? HttpResponse.json(
              { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
              { status: 500 },
            )
          : HttpResponse.json(workspace);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "작업 공간을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
    );
    await user.click(screen.getByRole("button", { name: "작업 공간 다시 불러오기" }));

    expect(
      await screen.findByRole("heading", { name: workspace.project.title }),
    ).toBeInTheDocument();
    expect(requestCount).toBe(2);
  });

  test("shows a project-not-found view without redirecting", async () => {
    renderWorkspace("/projects/missing-project/write");

    expect(
      await screen.findByRole("heading", { name: "프로젝트를 찾을 수 없어요" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "작품 서재로 돌아가기" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("retains tab URL state after closing the selected contextual tab in a mobile sheet", async () => {
    setViewportWidth(375);
    const user = userEvent.setup();
    const { router } = renderWorkspace();

    const charactersTab = await screen.findByRole("tab", { name: "인물 보기" });
    expect(screen.getAllByRole("tab")).toHaveLength(3);

    await user.click(charactersTab);

    const contextSheet = screen.getByRole("dialog", { name: "인물 보기" });
    expect(contextSheet).toHaveTextContent("등장인물");
    expect(contextSheet).toHaveTextContent("서윤");
    expect(charactersTab).toHaveAttribute("aria-selected", "true");

    await user.click(screen.getByRole("button", { name: "닫기" }));
    expect(screen.queryByRole("dialog", { name: "인물 보기" })).not.toBeInTheDocument();
    expect(charactersTab).toHaveAttribute("aria-selected", "true");
    expect(router.state.location.search).toEqual({ tab: "characters" });
  });

  test.each([
    ["characters", "인물 보기", "등장인물"],
    ["world", "세계관 보기", "세계관"],
  ])("restores the %s tab URL on direct navigation", async (tab, tabLabel, panelHeading) => {
    setViewportWidth(1024);
    const { router } = renderWorkspace(`/projects/silver-garden/write?tab=${tab}`);

    expect(await screen.findByRole("tab", { name: tabLabel, selected: true })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: panelHeading })).toBeInTheDocument();
    expect(router.state.location.search).toEqual({ tab });
  });

  test("uses manuscript for the default tab URL", async () => {
    setViewportWidth(1024);
    const { router } = renderWorkspace();

    expect(
      await screen.findByRole("tab", { name: "원고 보기", selected: true }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "원고 목차" })).toBeInTheDocument();
    expect(router.state.location.search).toEqual({});
  });

  test("uses vertical tab semantics for keyboard selection, URL updates, and wrapping", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace();

    const tablist = await screen.findByRole("tablist", { name: "집필 도메인" });
    const manuscriptTab = screen.getByRole("tab", { name: "원고 보기" });
    const charactersTab = screen.getByRole("tab", { name: "인물 보기" });
    const worldTab = screen.getByRole("tab", { name: "세계관 보기" });

    expect(tablist).toHaveAttribute("aria-orientation", "vertical");
    manuscriptTab.focus();

    await user.keyboard("{ArrowDown}");
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
    expect(charactersTab).toHaveFocus();
    expect(charactersTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "등장인물" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "원고 목차" })).not.toBeInTheDocument();

    await user.keyboard("{ArrowDown}");
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));
    expect(worldTab).toHaveFocus();
    expect(worldTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "세계관" })).toBeInTheDocument();

    await user.keyboard("{ArrowDown}");
    await waitFor(() => expect(router.state.location.search).toEqual({}));
    expect(manuscriptTab).toHaveFocus();
    expect(manuscriptTab).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowUp}");
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));
    expect(worldTab).toHaveFocus();
    expect(worldTab).toHaveAttribute("aria-selected", "true");
  });

  test("reconstructs initial protagonist editing from the URL with immutable ID and all fields", async () => {
    setViewportWidth(1024);
    const { router } = renderWorkspace(
      "/projects/silver-garden/write?panel=character-editor&characterId=silver-garden-character-1",
    );

    const dialog = await screen.findByRole("dialog", { name: "서윤 수정" });
    expect(dialog).toHaveClass("data-[side=right]:w-full", "data-[side=right]:sm:max-w-2xl");
    expect(dialog).not.toHaveClass("data-[side=right]:w-3/4", "data-[side=right]:sm:max-w-sm");
    await waitFor(() =>
      expect(router.state.location.search).toEqual({
        tab: "characters",
        panel: "character-editor",
        characterId: "silver-garden-character-1",
      }),
    );
    expect(within(dialog).getByLabelText("인물 ID")).toHaveValue("silver-garden-character-1");
    expect(within(dialog).getByLabelText("인물 ID")).toHaveAttribute("readonly");
    expect(within(dialog).getByRole("textbox", { name: "이름 *" })).toHaveValue("서윤");
    expect(within(dialog).getByRole("textbox", { name: "성별" })).toHaveValue("여성");
    expect(within(dialog).getByRole("textbox", { name: "나이" })).toHaveAttribute("type", "text");
    for (const label of ["역할", "성격", "문체", "대사 스타일", "기본 욕망", "숨은 감정"]) {
      expect(within(dialog).getByRole("textbox", { name: label })).toBeInTheDocument();
    }
    expect(dialog).not.toHaveTextContent("이전 기억");
    expect(dialog).not.toHaveTextContent("현재 욕망");
  });

  test("creates a character with all mutable fields, trusts the server ID, and preserves existing cards", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace("/projects/silver-garden/write?tab=characters");
    await user.click(await screen.findByRole("button", { name: "새 인물 등록" }));
    const dialog = screen.getByRole("dialog", { name: "새 인물 등록" });
    expect(dialog).toHaveClass("data-[side=right]:w-full", "data-[side=right]:sm:max-w-2xl");
    expect(within(dialog).queryByLabelText("인물 ID")).not.toBeInTheDocument();

    const values: Record<string, string> = {
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
      await user.type(within(dialog).getByRole("textbox", { name: label }), value);
    }
    await user.click(within(dialog).getByRole("button", { name: "저장" }));

    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
    expect(screen.getByRole("button", { name: "민서 인물 수정" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "서윤 인물 수정" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "도현 인물 수정" })).toBeInTheDocument();
    const status = screen.getByText("민서 인물을 저장했어요.");
    expect(status).toBeVisible();
    expect(status).toHaveAttribute("aria-live", "polite");
  });

  test("edits an initial protagonist and renders the authoritative last-save snapshot", async () => {
    setViewportWidth(1024);
    const workspace = getWorkspace();
    let requestBody: unknown;
    server.use(
      http.patch(
        "/api/projects/:projectId/story-bible/characters/:characterId",
        async ({ params, request }) => {
          expect(params.characterId).toBe("silver-garden-character-1");
          requestBody = await request.json();
          return HttpResponse.json({
            storyBibleRevision: 11,
            storyBible: {
              ...workspace.storyBible,
              characters: workspace.storyBible.characters.map((character) =>
                character.id === params.characterId
                  ? { ...character, name: "서버 서윤", hiddenFeeling: "서버가 확정한 마지막 감정" }
                  : character,
              ),
            },
          });
        },
      ),
    );
    const user = userEvent.setup();
    renderWorkspace(
      "/projects/silver-garden/write?tab=characters&panel=character-editor&characterId=silver-garden-character-1",
    );
    const feeling = await screen.findByRole("textbox", { name: "숨은 감정" });
    await user.clear(feeling);
    await user.type(feeling, "로컬 마지막 감정");
    await user.click(screen.getByRole("button", { name: "저장" }));

    expect(await screen.findByRole("button", { name: "서버 서윤 인물 수정" })).toBeInTheDocument();
    expect(screen.getByText(/서버가 확정한 마지막 감정/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "도현 인물 수정" })).toBeInTheDocument();
    expect(requestBody).toEqual({ hiddenFeeling: "로컬 마지막 감정" });
    expect(requestBody).not.toHaveProperty("id");
    expect(requestBody).not.toHaveProperty("expectedRevision");
  });

  test("shows normalized-name validation and focuses the name without submitting", async () => {
    setViewportWidth(1024);
    let requests = 0;
    server.use(
      http.post("/api/projects/:projectId/story-bible/characters", () => {
        requests += 1;
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=characters&panel=character-editor");
    const name = await screen.findByRole("textbox", { name: "이름 *" });
    await user.type(name, "   ");
    await user.click(screen.getByRole("button", { name: "저장" }));

    expect(screen.getByRole("alert")).toHaveTextContent("이름을 입력해 주세요.");
    expect(name).toHaveFocus();
    expect(requests).toBe(0);
  });

  test("uses product validation for an untouched empty create name", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=characters&panel=character-editor");
    const name = await screen.findByRole("textbox", { name: "이름 *" });
    const save = screen.getByRole("button", { name: "저장" });

    expect(save).toBeEnabled();
    await user.click(save);
    expect(screen.getByRole("alert")).toHaveTextContent("이름을 입력해 주세요.");
    expect(name).toHaveFocus();
  });

  test("does not treat whitespace-only changes to an existing name as a PATCH", async () => {
    setViewportWidth(1024);
    let requests = 0;
    server.use(
      http.patch("/api/projects/:projectId/story-bible/characters/:characterId", () => {
        requests += 1;
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    renderWorkspace(
      "/projects/silver-garden/write?tab=characters&panel=character-editor&characterId=silver-garden-character-1",
    );
    const name = await screen.findByRole("textbox", { name: "이름 *" });
    await user.type(name, "   ");

    expect(screen.getByRole("button", { name: "저장" })).toBeDisabled();
    expect(requests).toBe(0);
  });

  test("preserves a failed character draft and allows retry without duplicate submission", async () => {
    setViewportWidth(1024);
    let requests = 0;
    server.use(
      http.patch("/api/projects/:projectId/story-bible/characters/:characterId", async () => {
        requests += 1;
        await delay(20);
        return HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
          { status: 500 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWorkspace(
      "/projects/silver-garden/write?tab=characters&panel=character-editor&characterId=silver-garden-character-1",
    );
    const feeling = await screen.findByRole("textbox", { name: "숨은 감정" });
    await user.clear(feeling);
    await user.type(feeling, "실패 뒤에도 남는 초안");
    const save = screen.getByRole("button", { name: "저장" });
    await user.dblClick(save);

    expect(await screen.findByRole("alert")).toHaveTextContent("입력한 내용은 그대로 유지했어요");
    expect(feeling).toHaveValue("실패 뒤에도 남는 초안");
    expect(requests).toBe(1);
    await user.click(screen.getByRole("button", { name: "다시 저장" }));
    await waitFor(() => expect(requests).toBe(2));
  });

  test("guards dirty character close and tab navigation until discard is confirmed", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace(
      "/projects/silver-garden/write?tab=characters&panel=character-editor&characterId=silver-garden-character-1",
    );
    const personality = await screen.findByRole("textbox", { name: "성격" });
    await user.type(personality, " 지킬 초안");
    await expectUnloadProtection(router);
    await user.click(screen.getByRole("button", { name: "인물 편집기 닫기" }));
    expect(screen.getByRole("button", { name: "계속 편집" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "계속 편집" }));
    expect(personality).toHaveValue("단호하고 세심하다. 지킬 초안");
    expect(screen.getByRole("dialog", { name: "서윤 수정" })).toContainElement(
      document.activeElement as HTMLElement,
    );

    void router.navigate({
      to: "/projects/$projectId/write",
      params: { projectId: "silver-garden" },
      search: { tab: "world" },
    });
    expect(
      await screen.findByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" }),
    ).toBeInTheDocument();
    expect(router.state.location.search).toMatchObject({ tab: "characters" });
    await user.click(screen.getByRole("button", { name: "변경사항 버리기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));
  });

  test("keeps the character draft open when confirmed navigation is later blocked by manuscript flush", async () => {
    setViewportWidth(1024);
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "실패", fieldErrors: [] },
          { status: 500 },
        ),
      ),
    );
    const user = userEvent.setup();
    const { container, router } = renderWorkspace(
      "/projects/silver-garden/write?tab=characters&panel=character-editor&characterId=silver-garden-character-1",
    );
    const manuscript = await waitFor(() => {
      const element = container.querySelector<HTMLTextAreaElement>('[aria-label="원고 본문"]');
      expect(element).not.toBeNull();
      return element!;
    });
    fireEvent.change(manuscript, { target: { value: "탐색 전에 실패할 원고" } });
    const personality = await screen.findByRole("textbox", { name: "성격" });
    await user.type(personality, " 탐색 실패 뒤에도 남는 인물 초안");

    void router.navigate({ to: "/" });
    await user.click(await screen.findByRole("button", { name: "변경사항 버리기" }));

    await waitFor(() => expect(screen.getByText("저장 실패")).toBeInTheDocument());
    expect(screen.getByRole("textbox", { name: "성격" })).toHaveValue(
      "단호하고 세심하다. 탐색 실패 뒤에도 남는 인물 초안",
    );
    expect(router.state.location.search).toEqual({
      tab: "characters",
      panel: "character-editor",
      characterId: "silver-garden-character-1",
    });
  });

  test.each(["button", "escape", "overlay"] as const)(
    "completes a confirmed dirty %s close without reopening discard",
    async (closeMethod) => {
      setViewportWidth(1024);
      const user = userEvent.setup();
      const { router } = renderWorkspace(
        "/projects/silver-garden/write?tab=characters&panel=character-editor&characterId=silver-garden-character-1",
      );
      await user.type(await screen.findByRole("textbox", { name: "성격" }), " 폐기");
      if (closeMethod === "button") {
        await user.click(screen.getByRole("button", { name: "인물 편집기 닫기" }));
      } else if (closeMethod === "escape") {
        await user.keyboard("{Escape}");
      } else {
        const overlay = document.querySelector<HTMLElement>('[data-slot="sheet-overlay"]');
        expect(overlay).not.toBeNull();
        fireEvent.pointerDown(overlay!);
        fireEvent.click(overlay!);
      }
      await user.click(await screen.findByRole("button", { name: "변경사항 버리기" }));

      await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
      expect(screen.queryByRole("dialog", { name: "서윤 수정" })).not.toBeInTheDocument();
      expect(
        screen.queryByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" }),
      ).not.toBeInTheDocument();
    },
  );

  test("replays a clean character editor open through Back and Forward", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace("/projects/silver-garden/write?tab=characters");
    await user.click(await screen.findByRole("button", { name: "서윤 인물 수정" }));
    expect(await screen.findByRole("dialog", { name: "서윤 수정" })).toBeInTheDocument();

    router.history.back();
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
    expect(screen.queryByRole("dialog", { name: "서윤 수정" })).not.toBeInTheDocument();

    router.history.forward();
    expect(await screen.findByRole("dialog", { name: "서윤 수정" })).toBeInTheDocument();
  });

  test("blocks dirty browser Back until character discard is confirmed", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router, unmount } = renderBrowserWorkspace(
      "/projects/silver-garden/write?tab=characters",
    );
    await user.click(await screen.findByRole("button", { name: "서윤 인물 수정" }));
    await user.type(await screen.findByRole("textbox", { name: "성격" }), " 지킬 초안");
    await expectUnloadProtection(router);

    router.history.back();
    expect(
      await screen.findByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "계속 편집" }));
    expect(router.state.location.search).toMatchObject({ panel: "character-editor" });
    expect(screen.getByRole("textbox", { name: "성격" })).toHaveValue(
      "단호하고 세심하다. 지킬 초안",
    );
    expect(screen.getByRole("dialog", { name: "서윤 수정" })).toContainElement(
      document.activeElement as HTMLElement,
    );

    router.history.back();
    await user.click(await screen.findByRole("button", { name: "변경사항 버리기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));

    unmount();
    router.history.destroy();
  });

  test("restores focus inside a dirty create editor after cancelling discard", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace(
      "/projects/silver-garden/write?tab=characters&panel=character-editor",
    );
    const name = await screen.findByRole("textbox", { name: "이름 *" });
    await user.type(name, "지킬 신규 인물");

    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "계속 편집" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "계속 편집" }));

    expect(name).toHaveValue("지킬 신규 인물");
    expect(router.state.location.search).toEqual({
      tab: "characters",
      panel: "character-editor",
    });
    expect(screen.getByRole("dialog", { name: "새 인물 등록" })).toContainElement(
      document.activeElement as HTMLElement,
    );
  });

  test("models a character mutation 404 as unavailable while preserving the draft", async () => {
    setViewportWidth(1024);
    server.use(
      http.patch("/api/projects/:projectId/story-bible/characters/:characterId", () =>
        HttpResponse.json(
          { code: "CHARACTER_NOT_FOUND", message: "인물을 찾을 수 없습니다.", fieldErrors: [] },
          { status: 404 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWorkspace(
      "/projects/silver-garden/write?tab=characters&panel=character-editor&characterId=silver-garden-character-1",
    );
    const feeling = await screen.findByRole("textbox", { name: "숨은 감정" });
    await user.clear(feeling);
    await user.type(feeling, "404 뒤에도 남는 초안");
    await user.click(screen.getByRole("button", { name: "저장" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("더 이상 편집할 수 없어요");
    expect(feeling).toHaveValue("404 뒤에도 남는 초안");
    expect(feeling).toBeDisabled();
    expect(screen.getByRole("button", { name: "다시 저장" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "등장인물 목록으로 돌아가기" })).toBeInTheDocument();
  });

  test("stacks the character editor over mobile Context and restores launch focus", async () => {
    setViewportWidth(375);
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(await screen.findByRole("tab", { name: "인물 보기" }));
    expect(screen.getByRole("dialog", { name: "인물 보기" })).toBeInTheDocument();
    const launch = screen.getByRole("button", { name: "새 인물 등록" });
    await user.click(launch);

    expect(await screen.findByRole("dialog", { name: "새 인물 등록" })).toBeInTheDocument();
    expect(document.querySelectorAll('[data-slot="sheet-content"]')).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "인물 편집기 닫기" }));
    await waitFor(() => expect(launch).toHaveFocus());
    expect(screen.getByRole("dialog", { name: "인물 보기" })).toBeInTheDocument();
  });

  test("keeps document scrolling locked to the manuscript editor region", async () => {
    setViewportWidth(1024);
    const { container } = renderWorkspace();

    const manuscript = await screen.findByRole("textbox", { name: "원고 본문" });
    const editorRegion = manuscript.closest("main");
    const workspace = container.firstElementChild;

    expect(workspace).toHaveClass("h-svh", "overflow-hidden");
    expect(editorRegion).toHaveClass("min-h-0", "overflow-y-auto");
    expect(editorRegion?.parentElement).toHaveClass("min-h-0", "overflow-hidden");
  });

  test("opens the world editor from the populated read panel with canonical URL state", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace("/projects/silver-garden/write?tab=world");

    await user.click(await screen.findByRole("button", { name: "세계관 수정 및 추가" }));

    expect(screen.getByRole("dialog", { name: "세계관 수정 및 추가" })).toBeInTheDocument();
    expect(router.state.location.search).toEqual({ tab: "world", panel: "world-editor" });
    expect(screen.getByRole("textbox", { name: "기존 항목 1 제목" })).toBeInTheDocument();
  });

  test("reconstructs and canonicalizes the editor from direct URL state", async () => {
    setViewportWidth(1024);
    const { router } = renderWorkspace(
      "/projects/silver-garden/write?panel=world-editor&view=dense",
    );

    expect(await screen.findByRole("dialog", { name: "세계관 수정 및 추가" })).toBeInTheDocument();
    await waitFor(() =>
      expect(router.state.location.search).toEqual({
        view: "dense",
        tab: "world",
        panel: "world-editor",
      }),
    );
    expect(router.state.location.state.__TSR_index).toBe(0);
  });

  test("removes an unsupported editor panel while preserving world tab and unrelated search", async () => {
    setViewportWidth(1024);
    const { router } = renderWorkspace(
      "/projects/silver-garden/write?tab=world&panel=unknown&view=dense",
    );

    expect(
      await screen.findByRole("tab", { name: "세계관 보기", selected: true }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(router.state.location.search).toEqual({ tab: "world", view: "dense" }),
    );
    expect(router.state.location.state.__TSR_index).toBe(0);
  });

  test("pushes clean explicit close and reopens the editor through Back", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace("/projects/silver-garden/write?tab=world");
    await user.click(await screen.findByRole("button", { name: "세계관 수정 및 추가" }));
    await screen.findByRole("dialog", { name: "세계관 수정 및 추가" });
    await user.click(screen.getByRole("button", { name: "세계관 편집기 닫기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));

    router.history.back();
    expect(await screen.findByRole("dialog", { name: "세계관 수정 및 추가" })).toBeInTheDocument();
    expect(router.state.location.search).toEqual({ tab: "world", panel: "world-editor" });
  });

  test("pauses dirty URL navigation and resumes only after discard confirmation", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace("/projects/silver-garden/write?tab=world");
    await user.click(await screen.findByRole("button", { name: "세계관 수정 및 추가" }));
    const title = await screen.findByRole("textbox", { name: "기존 항목 1 제목" });
    await user.type(title, " 수정");
    await expectUnloadProtection(router);

    void router.navigate({
      to: "/projects/$projectId/write",
      params: { projectId: "silver-garden" },
      search: { tab: "world" },
    });
    expect(
      await screen.findByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" }),
    ).toBeInTheDocument();
    expect(router.state.location.search).toEqual({ tab: "world", panel: "world-editor" });
    await user.click(screen.getByRole("button", { name: "변경사항 버리기" }));

    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));
    expect(screen.queryByRole("dialog", { name: "세계관 수정 및 추가" })).not.toBeInTheDocument();
  });

  test("replays a successful confirmed navigation with a fresh authoritative world draft", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace("/projects/silver-garden/write?tab=world");
    await user.click(await screen.findByRole("button", { name: "세계관 수정 및 추가" }));
    const title = await screen.findByRole("textbox", { name: "기존 항목 1 제목" });
    const original = (title as HTMLInputElement).value;
    await user.clear(title);
    await user.type(title, "탐색에서 폐기할 초안");

    void router.navigate({
      to: "/projects/$projectId/write",
      params: { projectId: "silver-garden" },
      search: { tab: "world" },
    });
    await user.click(await screen.findByRole("button", { name: "변경사항 버리기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));

    router.history.back();
    expect(await screen.findByRole("textbox", { name: "기존 항목 1 제목" })).toHaveValue(original);
  });

  test("warns before unloading while the world editor has a dirty draft", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace(
      "/projects/silver-garden/write?tab=world&panel=world-editor",
    );
    await user.type(await screen.findByRole("textbox", { name: "기존 항목 1 제목" }), " 수정");

    await expectUnloadProtection(router);
  });

  test("shows an unavailable editor for a direct URL when the Story Bible is missing", async () => {
    setViewportWidth(1024);
    server.use(
      http.get("/api/projects/:projectId/story-bible", () =>
        HttpResponse.json(
          { code: "STORY_BIBLE_NOT_FOUND", message: "없음", fieldErrors: [] },
          { status: 404 },
        ),
      ),
    );
    renderWorkspace("/projects/silver-garden/write?tab=world&panel=world-editor");

    expect(await screen.findByRole("dialog", { name: "세계관 수정 및 추가" })).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "이 세계관을 더 이상 편집할 수 없어요",
    );
    expect(screen.getByRole("button", { name: "세계관 보기로 돌아가기" })).toBeInTheDocument();
  });

  test("returns initializing error close focus to the world tab for a direct editor URL", async () => {
    setViewportWidth(1024);
    server.use(
      http.get("/api/projects/:projectId/story-bible", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "실패", fieldErrors: [] },
          { status: 500 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=world&panel=world-editor");
    expect(await screen.findByRole("alert")).toHaveTextContent("세계관을 불러오지 못했어요");

    await user.click(screen.getByRole("button", { name: "닫기" }));

    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "세계관 보기", selected: true })).toHaveFocus(),
    );
  });

  test("guards a dirty explicit editor close and preserves the draft when cancelled", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace(
      "/projects/silver-garden/write?tab=world&panel=world-editor",
    );
    const title = await screen.findByRole("textbox", { name: "기존 항목 1 제목" });
    await user.clear(title);
    await user.type(title, "로컬 온실");

    const closeButton = screen.getByRole("button", { name: "세계관 편집기 닫기" });
    await user.click(closeButton);
    expect(
      screen.getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "계속 편집" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "계속 편집" }));

    expect(title).toHaveValue("로컬 온실");
    expect(router.state.location.search).toEqual({ tab: "world", panel: "world-editor" });
    expect(closeButton).toHaveFocus();
  });

  test("discards a confirmed close draft and reopens from the authoritative snapshot", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=world");
    const launch = await screen.findByRole("button", { name: "세계관 수정 및 추가" });
    await user.click(launch);
    const title = await screen.findByRole("textbox", { name: "기존 항목 1 제목" });
    const original = (title as HTMLInputElement).value;
    await user.clear(title);
    await user.type(title, "폐기할 로컬 초안");

    await user.click(screen.getByRole("button", { name: "세계관 편집기 닫기" }));
    await user.click(screen.getByRole("button", { name: "변경사항 버리기" }));
    await waitFor(() => expect(launch).toHaveFocus());
    await user.click(launch);

    expect(await screen.findByRole("textbox", { name: "기존 항목 1 제목" })).toHaveValue(original);
  });

  test("routes Escape and overlay dismissal through the dirty discard confirmation", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=world&panel=world-editor");
    const title = await screen.findByRole("textbox", { name: "기존 항목 1 제목" });
    await user.type(title, " 지킬 초안");

    await user.keyboard("{Escape}");
    expect(
      screen.getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" }),
    ).toBeInTheDocument();
    expect(document.querySelector('[data-slot="dialog-overlay"]')).toHaveClass("z-[70]");
    expect(document.querySelector('[data-slot="dialog-content"]')).toHaveClass("z-[71]");
    expect(screen.getByRole("button", { name: "계속 편집" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(title).toHaveValue("비가 그친 온실 지킬 초안");
    expect(title).toHaveFocus();

    const overlay = document.querySelector<HTMLElement>('[data-slot="sheet-overlay"]');
    expect(overlay).not.toBeNull();
    fireEvent.pointerDown(overlay!);
    fireEvent.click(overlay!);
    expect(
      screen.getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" }),
    ).toBeInTheDocument();
  });

  test("preserves and freezes a draft after save reports the Story Bible unavailable", async () => {
    setViewportWidth(1024);
    server.use(
      http.put("/api/projects/:projectId/story-bible/world-entries", () =>
        HttpResponse.json(
          { code: "STORY_BIBLE_NOT_FOUND", message: "없음", fieldErrors: [] },
          { status: 404 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=world&panel=world-editor");
    const title = await screen.findByRole("textbox", { name: "기존 항목 1 제목" });
    await user.clear(title);
    await user.type(title, "404 뒤에도 남는 초안");
    await user.click(screen.getByRole("button", { name: "저장" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("더 이상 편집할 수 없어요");
    expect(title).toHaveValue("404 뒤에도 남는 초안");
    expect(title).toBeDisabled();
    expect(screen.getByRole("button", { name: "세계관 항목 추가" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "세계관 보기로 돌아가기" }));
    expect(
      screen.getByRole("dialog", { name: "저장하지 않은 변경사항을 버릴까요?" }),
    ).toBeInTheDocument();
  });

  test("keeps the world draft open when confirmed navigation is later blocked by manuscript flush", async () => {
    setViewportWidth(1024);
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "실패", fieldErrors: [] },
          { status: 500 },
        ),
      ),
    );
    const user = userEvent.setup();
    const { container, router } = renderWorkspace(
      "/projects/silver-garden/write?tab=world&panel=world-editor",
    );
    const manuscript = await waitFor(() => {
      const element = container.querySelector<HTMLTextAreaElement>('[aria-label="원고 본문"]');
      expect(element).not.toBeNull();
      return element!;
    });
    fireEvent.change(manuscript, {
      target: { value: "탐색 전에 실패할 원고" },
    });
    const title = await screen.findByRole("textbox", { name: "기존 항목 1 제목" });
    await user.clear(title);
    await user.type(title, "탐색 실패 뒤에도 남는 세계관");

    void router.navigate({ to: "/" });
    await user.click(await screen.findByRole("button", { name: "변경사항 버리기" }));

    await waitFor(() => expect(screen.getByText("저장 실패")).toBeInTheDocument());
    expect(screen.getByRole("textbox", { name: "기존 항목 1 제목" })).toHaveValue(
      "탐색 실패 뒤에도 남는 세계관",
    );
    expect(router.state.location.search).toEqual({ tab: "world", panel: "world-editor" });
  });

  test("returns focus to the world tab after closing a direct-link editor", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=world&panel=world-editor");
    await screen.findByRole("textbox", { name: "기존 항목 1 제목" });

    await user.click(screen.getByRole("button", { name: "세계관 편집기 닫기" }));

    await waitFor(() =>
      expect(screen.getByRole("tab", { name: "세계관 보기", selected: true })).toHaveFocus(),
    );
  });

  test("adds multiple entries, focuses each new kind, validates all blanks, and focuses the first invalid title", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=world&panel=world-editor");
    await user.click(await screen.findByRole("button", { name: "세계관 항목 추가" }));
    expect(screen.getByRole("combobox", { name: "새 항목 1 분류" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "세계관 항목 추가" }));
    expect(screen.getByRole("combobox", { name: "새 항목 2 분류" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "저장" }));
    expect(screen.getByRole("alert")).toHaveTextContent("입력하지 않은 항목이 4개");
    expect(screen.getByRole("textbox", { name: "새 항목 1 제목" })).toHaveFocus();
    expect(screen.getAllByText("제목을 입력해 주세요.")).toHaveLength(2);
    expect(screen.getAllByText("설명을 입력해 주세요.")).toHaveLength(2);
  });

  test("saves normalized entries, uses the authoritative response, announces, and replacement-closes", async () => {
    setViewportWidth(1024);
    let request: SaveWorldEntriesRequest | undefined;
    const workspace = getWorkspace();
    const saved: StoryBibleSnapshot = {
      storyBibleRevision: 2,
      storyBible: {
        ...workspace.storyBible,
        worldEntries: [
          {
            ...workspace.storyBible.worldEntries[0],
            kind: "rule",
            title: "유리 온실",
            description: "수정된 설명",
          },
          {
            id: "server-world-2",
            kind: "object",
            title: "은빛 열쇠",
            description: "서버가 만든 항목",
          },
        ],
      },
    };
    server.use(
      http.put(
        "/api/projects/:projectId/story-bible/world-entries",
        async ({ request: incoming }) => {
          request = (await incoming.json()) as SaveWorldEntriesRequest;
          return HttpResponse.json(saved);
        },
      ),
    );
    const user = userEvent.setup();
    const { router } = renderWorkspace("/projects/silver-garden/write?tab=world");
    await user.click(await screen.findByRole("button", { name: "세계관 수정 및 추가" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "기존 항목 1 분류" }), "rule");
    const title = screen.getByRole("textbox", { name: "기존 항목 1 제목" });
    await user.clear(title);
    await user.type(title, "  유리 온실  ");
    const description = screen.getByRole("textbox", { name: "기존 항목 1 설명" });
    await user.clear(description);
    await user.type(description, " 수정된 설명 ");
    await user.click(screen.getByRole("button", { name: "세계관 항목 추가" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "새 항목 1 분류" }), "object");
    await user.type(screen.getByRole("textbox", { name: "새 항목 1 제목" }), " 은빛 열쇠 ");
    await user.type(screen.getByRole("textbox", { name: "새 항목 1 설명" }), " 서버가 만든 항목 ");
    await user.click(screen.getByRole("button", { name: "저장" }));

    expect(await screen.findByText("세계관을 저장했어요.")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));
    expect(screen.queryByRole("dialog", { name: "세계관 수정 및 추가" })).not.toBeInTheDocument();
    expect(screen.getByText("은빛 열쇠")).toBeInTheDocument();
    expect(screen.getByText("사물")).toBeInTheDocument();
    expect(request).toMatchObject({
      expectedRevision: 1,
      updates: [
        {
          id: workspace.storyBible.worldEntries[0].id,
          kind: "rule",
          title: "유리 온실",
          description: "수정된 설명",
        },
      ],
      additions: [{ kind: "object", title: "은빛 열쇠", description: "서버가 만든 항목" }],
    });
    expect(JSON.stringify(request)).not.toContain("new-");
    router.history.back();
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));
    expect(screen.queryByRole("dialog", { name: "세계관 수정 및 추가" })).not.toBeInTheDocument();
  });

  test("preserves the exact draft through a retryable save failure and retry", async () => {
    setViewportWidth(1024);
    let attempts = 0;
    server.use(
      http.put("/api/projects/:projectId/story-bible/world-entries", async ({ request }) => {
        attempts += 1;
        const body = (await request.json()) as SaveWorldEntriesRequest;
        if (attempts === 1)
          return HttpResponse.json(
            { code: "INTERNAL_ERROR", message: "실패", fieldErrors: [] },
            { status: 500 },
          );
        return HttpResponse.json({
          storyBibleRevision: 2,
          storyBible: { ...getWorkspace().storyBible, worldEntries: body.updates },
        });
      }),
    );
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=world&panel=world-editor");
    const title = await screen.findByRole("textbox", { name: "기존 항목 1 제목" });
    await user.clear(title);
    await user.type(title, "실패해도 남는 세계관");
    await user.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("편집 내용은 잃지 않았어요");
    expect(title).toHaveValue("실패해도 남는 세계관");
    await user.click(screen.getByRole("button", { name: "다시 시도" }));
    await waitFor(() => expect(attempts).toBe(2));
  });

  test("preserves conflict draft and replaces it only after confirmed latest reload succeeds", async () => {
    setViewportWidth(1024);
    const latest: StoryBibleSnapshot = {
      storyBibleRevision: 2,
      storyBible: {
        ...getWorkspace().storyBible,
        worldEntries: [{ ...getWorkspace().storyBible.worldEntries[0], title: "서버 최신 온실" }],
      },
    };
    let gets = 0;
    server.use(
      http.put("/api/projects/:projectId/story-bible/world-entries", () =>
        HttpResponse.json(
          { code: "STORY_BIBLE_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.get("/api/projects/:projectId/story-bible", () => {
        gets += 1;
        return HttpResponse.json(
          gets === 1 ? { storyBibleRevision: 1, storyBible: getWorkspace().storyBible } : latest,
        );
      }),
    );
    const user = userEvent.setup();
    renderWorkspace("/projects/silver-garden/write?tab=world&panel=world-editor");
    const title = await screen.findByRole("textbox", { name: "기존 항목 1 제목" });
    await user.clear(title);
    await user.type(title, "충돌한 로컬 초안");
    await user.click(screen.getByRole("button", { name: "저장" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("다른 곳에서 세계관이 변경되었어요");
    const reloadButton = screen.getByRole("button", { name: "최신 세계관 불러오기" });
    await user.click(reloadButton);
    expect(
      screen.getByRole("dialog", { name: "현재 편집 내용을 버리고 최신 세계관을 불러올까요?" }),
    ).toBeInTheDocument();
    expect(title).toHaveValue("충돌한 로컬 초안");
    await user.click(screen.getByRole("button", { name: "계속 편집" }));
    expect(title).toHaveValue("충돌한 로컬 초안");
    expect(reloadButton).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "최신 세계관 불러오기" }));
    await user.click(screen.getByRole("button", { name: "최신 세계관 불러오기" }));
    expect(await screen.findByRole("textbox", { name: "기존 항목 1 제목" })).toHaveValue(
      "서버 최신 온실",
    );
  });

  test("renders the editor above the mobile context sheet", async () => {
    setViewportWidth(375);
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(await screen.findByRole("tab", { name: "세계관 보기" }));
    expect(screen.getByRole("dialog", { name: "세계관 보기" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "세계관 수정 및 추가" }));
    expect(await screen.findByRole("dialog", { name: "세계관 수정 및 추가" })).toBeInTheDocument();
    expect(document.querySelectorAll('[data-slot="sheet-content"]')).toHaveLength(2);
  });

  test("writes canonical tab URL state while preserving unrelated search keys", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace("/projects/silver-garden/write?view=dense");

    await user.click(await screen.findByRole("tab", { name: "인물 보기" }));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({ view: "dense", tab: "characters" }),
    );

    await user.click(screen.getByRole("tab", { name: "세계관 보기" }));
    await waitFor(() =>
      expect(router.state.location.search).toEqual({ view: "dense", tab: "world" }),
    );
  });

  test("removes manuscript from tab URL state while preserving unrelated search keys", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace("/projects/silver-garden/write?tab=characters&view=dense");

    await user.click(await screen.findByRole("tab", { name: "원고 보기" }));

    await waitFor(() => expect(router.state.location.search).toEqual({ view: "dense" }));
    expect(screen.getByRole("tab", { name: "원고 보기", selected: true })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "원고 목차" })).toBeInTheDocument();
  });

  test("replays tab URL selection through browser history", async () => {
    setViewportWidth(1024);
    const user = userEvent.setup();
    const { router } = renderWorkspace();

    await user.click(await screen.findByRole("tab", { name: "인물 보기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
    await user.click(screen.getByRole("tab", { name: "세계관 보기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));

    router.history.back();
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
    expect(screen.getByRole("tab", { name: "인물 보기", selected: true })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "등장인물" })).toBeInTheDocument();

    router.history.back();
    await waitFor(() => expect(router.state.location.search).toEqual({}));
    expect(screen.getByRole("tab", { name: "원고 보기", selected: true })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "원고 목차" })).toBeInTheDocument();

    router.history.forward();
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
    expect(screen.getByRole("tab", { name: "인물 보기", selected: true })).toBeInTheDocument();

    router.history.forward();
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));
    expect(screen.getByRole("tab", { name: "세계관 보기", selected: true })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "세계관" })).toBeInTheDocument();
  });

  test("does not flush or block a tab URL click while the manuscript is unsaved", async () => {
    setViewportWidth(1024);
    let saveCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () => {
        saveCount += 1;
        return HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
          { status: 500 },
        );
      }),
    );
    const user = userEvent.setup();
    const { router } = renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });

    fireEvent.change(editor, { target: { value: "탭 이동으로 저장하지 않을 원고" } });
    expect(screen.getByRole("status")).toHaveAccessibleName("편집 중");
    await user.click(screen.getByRole("tab", { name: "인물 보기" }));

    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
    expect(screen.getByRole("tab", { name: "인물 보기", selected: true })).toBeInTheDocument();
    expect(saveCount).toBe(0);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("does not flush or block unsaved tab URL replay through browser history", async () => {
    setViewportWidth(1024);
    let saveCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () => {
        saveCount += 1;
        return HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        );
      }),
    );
    const user = userEvent.setup();
    const { router } = renderWorkspace();

    await user.click(await screen.findByRole("tab", { name: "인물 보기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
    await user.click(screen.getByRole("tab", { name: "세계관 보기" }));
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));

    const editor = screen.getByRole<HTMLTextAreaElement>("textbox", { name: "원고 본문" });
    fireEvent.change(editor, { target: { value: "히스토리 이동으로 저장하지 않을 원고" } });
    expect(screen.getByRole("status")).toHaveAccessibleName("편집 중");

    router.history.back();
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "characters" }));
    expect(screen.getByRole("tab", { name: "인물 보기", selected: true })).toBeInTheDocument();

    router.history.forward();
    await waitFor(() => expect(router.state.location.search).toEqual({ tab: "world" }));
    expect(screen.getByRole("tab", { name: "세계관 보기", selected: true })).toBeInTheDocument();
    expect(saveCount).toBe(0);
    expect(screen.queryByRole("dialog", { name: "원고 저장 충돌 해결" })).not.toBeInTheDocument();
  });

  test("still flushes and blocks an unsaved non-tab search navigation", async () => {
    let saveCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () => {
        saveCount += 1;
        return HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
          { status: 500 },
        );
      }),
    );
    const { router } = renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    fireEvent.change(editor, { target: { value: "검색 상태 이동 전에 저장할 원고" } });

    void router.navigate({
      to: "/projects/$projectId/write",
      params: { projectId: "silver-garden" },
      search: (previous) => ({ ...previous, view: "dense" }),
    });

    expect(await screen.findByRole("alert")).toHaveTextContent("저장 실패");
    expect(saveCount).toBe(1);
    expect(router.state.location.search).toEqual({});
    expect(editor.value).toBe("검색 상태 이동 전에 저장할 원고");
  });

  test.each([
    ["explicit manuscript", "tab=manuscript&view=dense"],
    ["empty", "tab=&view=dense"],
    ["repeated", "tab=characters&tab=world&view=dense"],
    ["non-string", "tab=true&view=dense"],
    ["unsupported", "tab=unknown&view=dense"],
  ])("canonicalizes %s tab URL input with replacement", async (_caseName, search) => {
    const { router } = renderWorkspace(`/projects/silver-garden/write?${search}`);

    expect(
      await screen.findByRole("tab", { name: "원고 보기", selected: true }),
    ).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.search).toEqual({ view: "dense" }));
    expect(router.state.location.state.__TSR_index).toBe(0);
  });

  test.each(["pending", "error", "not-found"])(
    "canonicalizes invalid tab URL state while the workspace query is %s",
    async (queryState) => {
      if (queryState === "pending") {
        server.use(
          http.get("/api/projects/:projectId/workspace", async () => {
            await delay("infinite");
            return HttpResponse.json({});
          }),
        );
      } else if (queryState === "error") {
        server.use(
          http.get("/api/projects/:projectId/workspace", () =>
            HttpResponse.json(
              { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
              { status: 500 },
            ),
          ),
        );
      }

      const projectId = queryState === "not-found" ? "missing-project" : "silver-garden";
      const { router } = renderWorkspace(`/projects/${projectId}/write?tab=unknown&view=dense`);

      if (queryState === "pending") {
        expect(await screen.findByRole("status")).toHaveTextContent(
          "작업 공간을 불러오는 중이에요.",
        );
      } else if (queryState === "error") {
        expect(await screen.findByRole("alert")).toHaveTextContent(
          "작업 공간을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
        );
      } else {
        expect(
          await screen.findByRole("heading", { name: "프로젝트를 찾을 수 없어요" }),
        ).toBeInTheDocument();
      }

      await waitFor(() => expect(router.state.location.search).toEqual({ view: "dense" }));
      expect(router.state.location.state.__TSR_index).toBe(0);
    },
  );

  test("keeps the AI tool within its mobile sheet and supports both close paths", async () => {
    setViewportWidth(375);
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "AI 도구 열기" }));
    const dialog = screen.getByRole("dialog", { name: "AI 집필 도구" });
    const panel = within(dialog).getByRole("heading", { name: "AI 집필 도구" }).closest("aside");
    expect(panel).toHaveClass("w-full", "min-w-0", "max-w-full");
    expect(panel).not.toHaveClass("w-[21rem]");

    await user.click(within(dialog).getByRole("button", { name: "AI 도구 닫기" }));
    expect(screen.queryByRole("dialog", { name: "AI 집필 도구" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));
    expect(screen.getByRole("dialog", { name: "AI 집필 도구" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "AI 집필 도구" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "원고 본문" })).toBeInTheDocument();
  });

  test("adds and selects scenes from the desktop workspace while saving the complete manuscript", async () => {
    setViewportWidth(1024);
    vi.stubGlobal("crypto", { randomUUID: () => "scene-2" });
    const saveRequests: SaveManuscriptRequest[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        saveRequests.push(body);
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        });
      }),
    );
    const workspace = getWorkspace();
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "새 장면 추가" }));

    expect(screen.getByRole("button", { name: "2장 제목 없는 장면" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByRole("heading", { name: "제목 없는 장면" })).toBeInTheDocument();
    expect(screen.getByText("2장 · 제목 없는 장면")).toBeInTheDocument();
    const editor = screen.getByRole("textbox", { name: "원고 본문" });
    await waitFor(() => expect(editor).toHaveFocus());
    expect(screen.getByText("2장 장면을 추가했어요")).toBeInTheDocument();
    await waitFor(() => expect(saveRequests[0]?.manuscript.scenes).toHaveLength(2));

    await user.click(screen.getByRole("button", { name: "1장 비가 그친 뒤의 정원" }));

    expect(screen.getByRole("button", { name: "1장 비가 그친 뒤의 정원" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByText("1장 · 비가 그친 뒤의 정원")).toBeInTheDocument();
    expect(screen.getByRole<HTMLTextAreaElement>("textbox", { name: "원고 본문" }).value).toBe(
      workspace.manuscript.scenes[0].content,
    );
    expect(screen.getByRole("button", { name: "2장 제목 없는 장면" })).toBeInTheDocument();
  });

  test("updates every active-scene title surface and autosaves the whole manuscript", async () => {
    setViewportWidth(1024);
    const requests: SaveManuscriptRequest[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-21T08:00:00.000Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "장면 제목 수정" }));
    const title = screen.getByRole("textbox", { name: "장면 제목" });
    await user.clear(title);
    await user.type(title, "  남겨진 편지  {Enter}");

    expectTitleSurfaces("남겨진 편지");
    await waitFor(() => expect(requests).toHaveLength(1), { timeout: 1_500 });
    expect(requests[0]!.manuscript.scenes[0]).toMatchObject({
      title: "남겨진 편지",
      content: expect.stringContaining("비가 그친 뒤의 온실"),
    });
  });

  test("keeps a failed title locally and retries the same whole manuscript", async () => {
    setViewportWidth(1024);
    const requests: SaveManuscriptRequest[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        if (requests.length === 1) {
          return HttpResponse.json(
            { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
            { status: 500 },
          );
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-21T08:00:00.000Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "장면 제목 수정" }));
    const title = screen.getByRole("textbox", { name: "장면 제목" });
    await user.clear(title);
    await user.type(title, "실패해도 남는 제목{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("저장 실패");
    expectTitleSurfaces("실패해도 남는 제목");
    await user.click(screen.getByRole("button", { name: "원고 저장 다시 시도" }));

    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1]!.manuscript.scenes[0]!.title).toBe("실패해도 남는 제목");
  });

  test("disables title editing during conflict and applies the server title everywhere", async () => {
    setViewportWidth(1024);
    const workspace = getWorkspace();
    const serverManuscript = {
      ...workspace.manuscript,
      scenes: workspace.manuscript.scenes.map((scene) => ({
        ...scene,
        title: scene.id === workspace.manuscript.activeSceneId ? "서버 최신 제목" : scene.title,
      })),
    };
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json({
          sceneId: body.sceneId,
          serverRevision: 2,
          localContent: body.localContent,
          serverContent: workspace.manuscript.scenes[0]!.content,
          serverManuscript,
          rows: [],
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "장면 제목 수정" }));
    const title = screen.getByRole("textbox", { name: "장면 제목" });
    await user.clear(title);
    await user.type(title, "충돌한 로컬 제목{Enter}");

    expect(await screen.findByText("저장 충돌")).toBeInTheDocument();
    await screen.findByRole("button", { name: "서버 최신본 적용" });
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "장면 제목 수정" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "충돌 해결 열기" }));
    await user.click(screen.getByRole("button", { name: "서버 최신본 적용" }));

    expectTitleSurfaces("서버 최신 제목");
    expect(screen.getByRole("button", { name: "장면 제목 수정" })).toBeEnabled();
  });

  test("keeps the local title on every surface when resolving a conflict with my draft", async () => {
    setViewportWidth(1024);
    const workspace = getWorkspace();
    const activeScene = workspace.manuscript.scenes[0]!;
    const requests: SaveManuscriptRequest[] = [];
    const serverManuscript = {
      ...workspace.manuscript,
      scenes: [{ ...activeScene, title: "서버 최신 제목", content: "서버 최신 본문" }],
    };
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        if (requests.length === 1) {
          return HttpResponse.json(
            { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
            { status: 409 },
          );
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 8,
          projectActivity: {
            projectId: workspace.project.id,
            updatedAt: "2026-07-22T01:00:00.000Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json({
          sceneId: body.sceneId,
          serverRevision: 7,
          localContent: body.localContent,
          serverContent: "서버 최신 본문",
          serverManuscript,
          rows: [],
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "장면 제목 수정" }));
    const title = screen.getByRole("textbox", { name: "장면 제목" });
    await user.clear(title);
    await user.type(title, "내가 유지할 제목{Enter}");
    await user.click(await screen.findByRole("button", { name: "내 편집본 유지" }));

    await waitFor(() => expect(requests).toHaveLength(2));
    expect(requests[1]!.manuscript.scenes[0]!.title).toBe("내가 유지할 제목");
    expectTitleSurfaces("내가 유지할 제목");
  });

  test("discards an uncommitted title when selecting another scene", async () => {
    setViewportWidth(1024);
    const workspace = getWorkspace();
    const manuscript = {
      ...workspace.manuscript,
      scenes: [
        ...workspace.manuscript.scenes,
        {
          id: "scene-2",
          title: "두 번째 장면",
          chapterNumber: 2,
          content: "두 번째 본문",
          relatedCharacterIds: [],
          relatedWorldEntryIds: [],
        },
      ],
    };
    const requests: SaveManuscriptRequest[] = [];
    server.use(
      http.get("/api/projects/:projectId/workspace", () =>
        HttpResponse.json({ ...workspace, manuscript }),
      ),
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-21T08:00:00.000Z",
          },
        } satisfies SaveManuscriptResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "장면 제목 수정" }));
    const title = screen.getByRole("textbox", { name: "장면 제목" });
    await user.clear(title);
    await user.type(title, "저장하면 안 되는 제목");
    await user.click(screen.getByRole("button", { name: "2장 두 번째 장면" }));

    expectTitleSurfaces("두 번째 장면", 2);
    expect(screen.queryByDisplayValue("저장하면 안 되는 제목")).not.toBeInTheDocument();
    await waitFor(() => expect(requests.length).toBeGreaterThan(0));
    expect(
      requests.every(({ manuscript: saved }) => saved.scenes[0]!.title === "비가 그친 뒤의 정원"),
    ).toBe(true);
  });

  test.each([375, 1024])("edits and synchronizes a scene title at %dpx", async (viewportWidth) => {
    setViewportWidth(viewportWidth);
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "장면 제목 수정" }));
    const title = screen.getByRole("textbox", { name: "장면 제목" });
    await user.clear(title);
    await user.type(title, `반응형 제목 ${viewportWidth.toString()}{Enter}`);

    expect(
      screen.getByRole("heading", { name: `반응형 제목 ${viewportWidth.toString()}` }),
    ).toBeInTheDocument();
    expect(screen.getByText(`1장 · 반응형 제목 ${viewportWidth.toString()}`)).toBeInTheDocument();
    if (viewportWidth === 375) {
      await user.click(screen.getByRole("tab", { name: "원고 보기" }));
    }
    expect(
      screen.getByRole("button", { name: `1장 반응형 제목 ${viewportWidth.toString()}` }),
    ).toBeInTheDocument();
  });

  test("closes the mobile manuscript sheet and focuses the editor after adding a scene", async () => {
    setViewportWidth(375);
    vi.stubGlobal("crypto", { randomUUID: () => "scene-2" });
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("tab", { name: "원고 보기" }));
    expect(screen.getByRole("dialog", { name: "원고 보기" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "새 장면 추가" }));

    expect(screen.queryByRole("dialog", { name: "원고 보기" })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("textbox", { name: "원고 본문" })).toHaveFocus());
  });

  test("disables scene addition while resolving a structural conflict", async () => {
    setViewportWidth(1024);
    vi.stubGlobal("crypto", { randomUUID: () => "scene-2" });
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const addSceneButton = await screen.findByRole("button", { name: "새 장면 추가" });

    await user.click(addSceneButton);

    expect(await screen.findByRole("dialog", { name: "원고 저장 충돌 해결" })).toBeInTheDocument();
    expect(addSceneButton).toBeDisabled();
  });

  test("keeps scene addition available after a save error and retries with the new scene", async () => {
    setViewportWidth(1024);
    vi.stubGlobal("crypto", { randomUUID: () => "scene-2" });
    const saveRequests: SaveManuscriptRequest[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        saveRequests.push(body);
        if (saveRequests.length === 1) {
          return HttpResponse.json(
            { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
            { status: 500 },
          );
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        });
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(await screen.findByRole("button", { name: "새 장면 추가" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("저장 실패");
    expect(screen.getByRole("button", { name: "새 장면 추가" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "2장 제목 없는 장면" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "원고 저장 다시 시도" }));

    await waitFor(() => expect(saveRequests).toHaveLength(2));
    expect(saveRequests[1].manuscript.scenes).toHaveLength(2);
    expect(saveRequests[1].manuscript.activeSceneId).toBe(saveRequests[1].manuscript.scenes[1].id);
  });

  test("restores the saved active scene from a reload-equivalent workspace response", async () => {
    setViewportWidth(1024);
    const workspace = getWorkspace();
    const restoredWorkspace: ProjectWorkspaceResponse = {
      ...workspace,
      manuscript: {
        ...workspace.manuscript,
        activeSceneId: "scene-2",
        scenes: [
          ...workspace.manuscript.scenes,
          {
            id: "scene-2",
            title: "제목 없는 장면",
            chapterNumber: 2,
            content: "복원된 두 번째 장면",
            relatedCharacterIds: [],
            relatedWorldEntryIds: [],
          },
        ],
      },
      manuscriptRevision: 2,
    };
    server.use(
      http.get("/api/projects/:projectId/workspace", () => HttpResponse.json(restoredWorkspace)),
    );

    renderWorkspace();

    expect(await screen.findByRole("button", { name: "2장 제목 없는 장면" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByText("2장 · 제목 없는 장면")).toBeInTheDocument();
    expect(screen.getByRole<HTMLTextAreaElement>("textbox", { name: "원고 본문" }).value).toBe(
      "복원된 두 번째 장면",
    );
  });

  test("adds a resize handle only for each visible adjacent desktop panel", async () => {
    setViewportWidth(1280);
    const user = userEvent.setup();
    renderWorkspace();

    await screen.findByRole("textbox", { name: "원고 본문" });
    expect(screen.getAllByRole("separator")).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));
    expect(screen.queryByRole("dialog", { name: "AI 집필 도구" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("separator")).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "AI 도구 닫기" }));
    expect(screen.getAllByRole("separator")).toHaveLength(1);
  });

  test("distributes every visible desktop panel across the resizable layout", async () => {
    setViewportWidth(1280);
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(500);
    const user = userEvent.setup();
    const { container } = renderWorkspace();

    await screen.findByRole("textbox", { name: "원고 본문" });
    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));
    const panels = container.querySelectorAll<HTMLElement>('[data-slot="resizable-panel"]');
    expect(panels).toHaveLength(3);
    await waitFor(() => {
      expect(panels[0]).toHaveStyle({ flexGrow: "20" });
      expect(panels[1]).toHaveStyle({ flexGrow: "55" });
      expect(panels[2]).toHaveStyle({ flexGrow: "25" });
    });
  });

  test("resizes desktop panels from a focused separator with the keyboard", async () => {
    setViewportWidth(1280);
    vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(500);
    const user = userEvent.setup();
    renderWorkspace();

    await screen.findByRole("textbox", { name: "원고 본문" });
    const separator = screen.getByRole("separator");
    const initialSize = separator.getAttribute("aria-valuenow");

    separator.focus();
    expect(separator).toHaveFocus();
    expect(separator).toHaveAttribute("tabindex", "0");
    await user.keyboard("{ArrowRight}");

    await waitFor(() => expect(separator).not.toHaveAttribute("aria-valuenow", initialSize));
  });

  test("applies a requested continuation to the manuscript", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole("textbox", { name: "원고 본문" });
    const original = (editor as HTMLTextAreaElement).value;

    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));

    expect(screen.getByRole("heading", { name: "AI 집필 도구" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "문장 다듬기" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "이어 쓰기" }));
    expect(screen.getByText("다음 문단 제안")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "원고에 적용" }));

    expect((editor as HTMLTextAreaElement).value.length).toBeGreaterThan(original.length);
  });

  test("enables sentence refinement only for selected manuscript text", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    const original = editor.value;

    editor.setSelectionRange(0, 8);
    fireEvent.select(editor);
    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));

    const refine = screen.getByRole("button", { name: "문장 다듬기" });
    expect(refine).toBeEnabled();

    await user.click(refine);
    expect(screen.getByText("감정을 보여주는 문장")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "원고에 적용" }));

    expect(editor.value).not.toBe(original);
  });

  test("inserts a continuation at the current cursor, including position zero", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });

    editor.setSelectionRange(0, 0);
    fireEvent.select(editor);
    await user.click(screen.getByRole("button", { name: "AI 도구 열기" }));
    await user.click(screen.getByRole("button", { name: "이어 쓰기" }));
    await user.click(screen.getByRole("button", { name: "원고에 적용" }));

    expect(editor.value).toMatch(/^\n\n/);
  });

  test.each(["mouse", "keyboard"] as const)(
    "restores editor focus and selection after a successful %s retry",
    async (activation) => {
      let saveCount = 0;
      server.use(
        http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
          saveCount += 1;
          const body = (await request.json()) as SaveManuscriptRequest;
          if (saveCount === 1) {
            return HttpResponse.json(
              { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
              { status: 500 },
            );
          }

          return HttpResponse.json({
            manuscript: body.manuscript,
            manuscriptRevision: 2,
            projectActivity: {
              projectId: body.manuscript.projectId,
              updatedAt: "2026-07-14T03:00:00.000Z",
            },
          });
        }),
      );
      const user = userEvent.setup();
      renderWorkspace();
      const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
        name: "원고 본문",
      });
      expect(screen.getByRole("status")).toHaveAccessibleName("자동 저장됨");

      fireEvent.change(editor, { target: { value: "저장에 실패해도 남는 원고" } });
      expect(screen.getByRole("status")).toHaveAccessibleName("편집 중");

      expect(await screen.findByRole("alert")).toHaveTextContent("저장 실패");
      expect(editor.value).toBe("저장에 실패해도 남는 원고");
      editor.setSelectionRange(3, 8);
      const retryButton = screen.getByRole("button", { name: "원고 저장 다시 시도" });
      if (activation === "mouse") {
        await user.click(retryButton);
      } else {
        screen.getByRole("link", { name: "작품 서재로 돌아가기" }).focus();
        await user.tab();
        expect(retryButton).toHaveFocus();
        await user.keyboard("{Enter}");
      }

      expect(await screen.findByRole("status")).toHaveAccessibleName("자동 저장됨");
      await waitFor(() => expect(editor).toHaveFocus());
      expect(editor.value).toBe("저장에 실패해도 남는 원고");
      expect(editor.selectionStart).toBe(3);
      expect(editor.selectionEnd).toBe(8);
      expect(saveCount).toBe(2);
    },
  );

  test("keeps the retry alert and focus when a retry fails again", async () => {
    let saveCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () => {
        saveCount += 1;
        return HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
          { status: 500 },
        );
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    fireEvent.change(editor, { target: { value: "재시도도 실패하는 원고" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("저장 실패");
    const retryButton = screen.getByRole("button", { name: "원고 저장 다시 시도" });

    await user.click(retryButton);

    await waitFor(() => expect(saveCount).toBe(2));
    expect(screen.getByRole("alert")).toHaveTextContent("저장 실패");
    expect(screen.getByRole("button", { name: "원고 저장 다시 시도" })).toBeInTheDocument();
    expect(editor).not.toHaveFocus();
    expect(editor.value).toBe("재시도도 실패하는 원고");
  });

  test("saves an edit immediately before internal navigation and proceeds only after success", async () => {
    const requests: SaveManuscriptRequest[] = [];
    let releaseSave!: () => void;
    const saveBarrier = new Promise<void>((resolve) => {
      releaseSave = resolve;
    });
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        await saveBarrier;
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 2,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        });
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });

    fireEvent.change(editor, { target: { value: "탐색 전에 저장할 원고" } });
    await user.click(screen.getByRole("link", { name: "작품 서재로 돌아가기" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(screen.getByRole("heading", { name: getWorkspace().project.title })).toBeInTheDocument();
    expect(requests[0].manuscript.scenes[0].content).toBe("탐색 전에 저장할 원고");

    releaseSave();
    expect(
      await screen.findByRole("heading", { name: "다시, 이야기를 시작해 볼까요?" }),
    ).toBeInTheDocument();
  });

  test("saves a newer edit queued behind an active save before navigating", async () => {
    const requests: SaveManuscriptRequest[] = [];
    let releaseFirstSave!: () => void;
    const firstSaveBarrier = new Promise<void>((resolve) => {
      releaseFirstSave = resolve;
    });
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        requests.push(body);
        if (requests.length === 1) {
          await firstSaveBarrier;
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: requests.length + 1,
          projectActivity: {
            projectId: body.manuscript.projectId,
            updatedAt: "2026-07-14T03:00:00.000Z",
          },
        });
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });

    fireEvent.change(editor, { target: { value: "첫 저장 원고" } });
    await waitFor(() => expect(requests).toHaveLength(1), { timeout: 2_000 });
    fireEvent.change(editor, { target: { value: "뒤에 대기한 최신 원고" } });
    await user.click(screen.getByRole("link", { name: "작품 서재로 돌아가기" }));

    expect(screen.getByRole("heading", { name: getWorkspace().project.title })).toBeInTheDocument();
    releaseFirstSave();
    expect(
      await screen.findByRole("heading", { name: "다시, 이야기를 시작해 볼까요?" }),
    ).toBeInTheDocument();
    expect(requests).toHaveLength(2);
    expect(requests[1].expectedRevision).toBe(2);
    expect(requests[1].manuscript.scenes[0].content).toBe("뒤에 대기한 최신 원고");
  });

  test("warns before unloading while the manuscript has unsaved work", async () => {
    const { router } = renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    fireEvent.change(editor, { target: { value: "닫기 전에 지킬 원고" } });

    await expectUnloadProtection(router);
  });

  test("cancels internal navigation when the immediate save fails and exposes retry", async () => {
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
          { status: 500 },
        ),
      ),
    );
    const user = userEvent.setup();
    const { router } = renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    fireEvent.change(editor, { target: { value: "실패해도 지킬 원고" } });

    await user.click(screen.getByRole("link", { name: "작품 서재로 돌아가기" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("저장 실패");
    expect(screen.getByRole("button", { name: "원고 저장 다시 시도" })).toBeInTheDocument();
    expect(editor.value).toBe("실패해도 지킬 원고");
    await expectUnloadProtection(router);
  });

  test("cancels internal navigation when saving finds a conflict", async () => {
    const workspace = getWorkspace();
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json({
          sceneId: body.sceneId,
          serverRevision: 2,
          localContent: body.localContent,
          serverContent: workspace.manuscript.scenes[0].content,
          serverManuscript: workspace.manuscript,
          rows: [],
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const user = userEvent.setup();
    const { router } = renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    fireEvent.change(editor, { target: { value: "충돌해도 지킬 원고" } });

    await user.click(screen.getByRole("link", { name: "작품 서재로 돌아가기" }));

    expect(await screen.findByRole("dialog", { name: "원고 저장 충돌 해결" })).toBeInTheDocument();
    expect(editor.value).toBe("충돌해도 지킬 원고");
    await expectUnloadProtection(router);
  });

  test("opens the conflict comparison and Escape closes it without discarding the draft", async () => {
    const workspace = getWorkspace();
    let compareCount = 0;
    server.use(
      http.put("/api/manuscripts/:manuscriptId", () =>
        HttpResponse.json(
          { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
          { status: 409 },
        ),
      ),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        compareCount += 1;
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json({
          sceneId: body.sceneId,
          serverRevision: 2,
          localContent: body.localContent,
          serverContent: "서버 최신 장면",
          serverManuscript: {
            ...workspace.manuscript,
            scenes: workspace.manuscript.scenes.map((scene) =>
              scene.id === body.sceneId ? { ...scene, content: "서버 최신 장면" } : scene,
            ),
          },
          rows: [
            {
              kind: "local-only",
              localLineNumber: 1,
              localText: body.localContent,
              serverLineNumber: null,
              serverText: null,
            },
            {
              kind: "server-only",
              localLineNumber: null,
              localText: null,
              serverLineNumber: 1,
              serverText: "서버 최신 장면",
            },
          ],
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", { name: "원고 본문" });

    fireEvent.change(editor, { target: { value: "Escape 뒤에도 남는 로컬 장면" } });
    expect(await screen.findByRole("dialog", { name: "원고 저장 충돌 해결" })).toBeInTheDocument();
    expect(await screen.findByRole("columnheader", { name: "내 편집본" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "서버 최신본" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "내 편집본 유지" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "서버 최신본 적용" })).toBeEnabled();
    expect(compareCount).toBe(1);

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "원고 저장 충돌 해결" })).not.toBeInTheDocument();
    expect(editor.value).toBe("Escape 뒤에도 남는 로컬 장면");
  });

  test("keeps the modal locked during local resolution and safely adopts its successful save", async () => {
    const workspace = getWorkspace();
    let saveCount = 0;
    let releaseResolution!: () => void;
    const resolutionBarrier = new Promise<void>((resolve) => {
      releaseResolution = resolve;
    });
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        saveCount += 1;
        const body = (await request.json()) as SaveManuscriptRequest;
        if (saveCount === 1) {
          return HttpResponse.json(
            { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
            { status: 409 },
          );
        }
        await resolutionBarrier;
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 3,
          projectActivity: {
            projectId: workspace.project.id,
            updatedAt: "2026-07-14T06:00:00Z",
          },
        });
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json({
          sceneId: body.sceneId,
          serverRevision: 2,
          localContent: body.localContent,
          serverContent: "서버 최신 장면",
          serverManuscript: {
            ...workspace.manuscript,
            scenes: workspace.manuscript.scenes.map((scene) =>
              scene.id === body.sceneId ? { ...scene, content: "서버 최신 장면" } : scene,
            ),
          },
          rows: [],
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", { name: "원고 본문" });
    fireEvent.change(editor, { target: { value: "해결 응답까지 지킬 로컬 장면" } });
    await screen.findByRole("dialog", { name: "원고 저장 충돌 해결" });

    await user.click(screen.getByRole("button", { name: "내 편집본 유지" }));
    expect(screen.queryByRole("textbox", { name: "원고 본문" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: "원고 저장 충돌 해결" })).toBeInTheDocument();

    releaseResolution();
    const restoredEditor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    expect(restoredEditor.value).toBe("해결 응답까지 지킬 로컬 장면");
    expect(screen.queryByRole("dialog", { name: "원고 저장 충돌 해결" })).not.toBeInTheDocument();
    expect(saveCount).toBe(2);
  });

  test("restores conflict retry focus after a failed resolution and returns focus to the draft after retry", async () => {
    const workspace = getWorkspace();
    const savedRequests: SaveManuscriptRequest[] = [];
    server.use(
      http.put("/api/manuscripts/:manuscriptId", async ({ request }) => {
        const body = (await request.json()) as SaveManuscriptRequest;
        savedRequests.push(body);
        if (savedRequests.length === 1) {
          return HttpResponse.json(
            { code: "MANUSCRIPT_REVISION_CONFLICT", message: "충돌", fieldErrors: [] },
            { status: 409 },
          );
        }
        if (savedRequests.length === 2) {
          return HttpResponse.json(
            { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요.", fieldErrors: [] },
            { status: 500 },
          );
        }
        return HttpResponse.json({
          manuscript: body.manuscript,
          manuscriptRevision: 3,
          projectActivity: {
            projectId: workspace.project.id,
            updatedAt: "2026-07-14T06:00:00Z",
          },
        });
      }),
      http.post("/api/manuscripts/:manuscriptId/scene-diffs", async ({ request }) => {
        const body = (await request.json()) as { sceneId: string; localContent: string };
        return HttpResponse.json({
          sceneId: body.sceneId,
          serverRevision: 2,
          localContent: body.localContent,
          serverContent: "서버 최신 장면",
          serverManuscript: {
            ...workspace.manuscript,
            scenes: workspace.manuscript.scenes.map((scene) =>
              scene.id === body.sceneId ? { ...scene, content: "서버 최신 장면" } : scene,
            ),
          },
          rows: [],
        } satisfies CompareManuscriptSceneResponse);
      }),
    );
    const user = userEvent.setup();
    renderWorkspace();
    const editor = await screen.findByRole<HTMLTextAreaElement>("textbox", { name: "원고 본문" });
    const localDraft = "포커스와 선택 범위를 지킬 로컬 장면";
    editor.focus();
    fireEvent.change(editor, { target: { value: localDraft } });
    editor.setSelectionRange(4, 10);
    await screen.findByRole("dialog", { name: "원고 저장 충돌 해결" });

    await user.click(screen.getByRole("button", { name: "내 편집본 유지" }));
    const retry = await screen.findByRole("button", { name: "내 편집본 저장 다시 시도" });
    await waitFor(() => expect(retry).toHaveFocus());
    expect(screen.getByRole("alert")).toHaveTextContent("내 편집본을 서버에 저장하지 못했어요");

    await user.click(retry);
    const restoredEditor = await screen.findByRole<HTMLTextAreaElement>("textbox", {
      name: "원고 본문",
    });
    await waitFor(() => expect(restoredEditor).toHaveFocus());
    expect(restoredEditor.value).toBe(localDraft);
    expect(restoredEditor.selectionStart).toBe(4);
    expect(restoredEditor.selectionEnd).toBe(10);
    expect(savedRequests).toHaveLength(3);
    expect(savedRequests[1].expectedRevision).toBe(2);
    expect(savedRequests[2].expectedRevision).toBe(2);
  });
});

function renderWorkspace(initialUrl = "/projects/silver-garden/write") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppMemoryRouter([initialUrl]);
  vi.spyOn(router.history, "block");

  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
    router,
  };
}

function renderBrowserWorkspace(initialUrl: string) {
  window.history.replaceState({}, "", initialUrl);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const router = createAppRouter({ history: createBrowserHistory() });
  vi.spyOn(router.history, "block");

  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
    router,
  };
}

async function expectUnloadProtection(router: ReturnType<typeof createAppMemoryRouter>) {
  await waitFor(() => {
    expect(router.history.block).toHaveBeenLastCalledWith(
      expect.objectContaining({ enableBeforeUnload: true }),
    );
  });
}

function getWorkspace(): ProjectWorkspaceResponse {
  const workspace = findMockWorkspace("silver-garden");
  if (!workspace) {
    throw new Error("Expected the seeded workspace");
  }
  return workspace;
}

function expectTitleSurfaces(title: string, chapterNumber = 1) {
  expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
  expect(screen.getByText(`${chapterNumber.toString()}장 · ${title}`)).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: `${chapterNumber.toString()}장 ${title}` }),
  ).toBeInTheDocument();
}
