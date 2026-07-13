import { describe, expect, test } from "vitest";

describe("applyWritingSuggestion", () => {
  test("applies insertion suggestions at the cursor", async () => {
    const { applyWritingSuggestion } = await import("./apply-writing-suggestion");
    const { createInitialManuscript, updateSceneContent } = await import("@/modules/manuscript");
    const manuscript = updateSceneContent(
      createInitialManuscript("project-1"),
      "project-1-scene-1",
      "앞뒤",
    );

    const updated = applyWritingSuggestion({
      manuscript,
      sceneId: "project-1-scene-1",
      suggestion: {
        id: "suggestion-1",
        action: "continue",
        kind: "insert",
        title: "이어 쓰기",
        content: "사이",
      },
      cursorPosition: 1,
      selectedRange: null,
    });

    expect(updated.scenes[0]?.content).toBe("앞사이뒤");
  });

  test("uses the captured selection for replacement suggestions", async () => {
    const { applyWritingSuggestion } = await import("./apply-writing-suggestion");
    const { createInitialManuscript, updateSceneContent } = await import("@/modules/manuscript");
    const manuscript = updateSceneContent(
      createInitialManuscript("project-1"),
      "project-1-scene-1",
      "그는 웃었다.",
    );

    const updated = applyWritingSuggestion({
      manuscript,
      sceneId: "project-1-scene-1",
      suggestion: {
        id: "suggestion-1",
        action: "refine",
        kind: "replace",
        title: "다듬기",
        content: "미소 지었다",
      },
      cursorPosition: 0,
      selectedRange: { start: 3, end: 6 },
    });

    expect(updated.scenes[0]?.content).toBe("그는 미소 지었다.");
  });

  test("does not mutate manuscripts for diagnostics", async () => {
    const { applyWritingSuggestion } = await import("./apply-writing-suggestion");
    const { createInitialManuscript } = await import("@/modules/manuscript");
    const manuscript = createInitialManuscript("project-1");

    expect(
      applyWritingSuggestion({
        manuscript,
        sceneId: manuscript.activeSceneId,
        suggestion: {
          id: "suggestion-1",
          action: "consistency",
          kind: "diagnostic",
          title: "검사",
          content: "문제 없음",
        },
        cursorPosition: 0,
        selectedRange: null,
      }),
    ).toBe(manuscript);
  });
});
