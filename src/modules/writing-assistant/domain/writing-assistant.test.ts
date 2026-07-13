import { describe, expect, test } from "vitest";

describe("Writing assistant", () => {
  test("returns an insertion without changing the manuscript", async () => {
    const { createWritingSuggestion } = await import("./writing-assistant");
    const request = {
      action: "continue" as const,
      sceneContent: "서윤은 편지를 접었다.",
      selectedText: "",
      characterNames: ["서윤", "도현"],
    };

    const suggestion = createWritingSuggestion(request);

    expect(suggestion.kind).toBe("insert");
    expect(suggestion.content).toContain("도현");
    expect(request.sceneContent).toBe("서윤은 편지를 접었다.");
  });

  test("requires selected text before refining", async () => {
    const { createWritingSuggestion } = await import("./writing-assistant");

    expect(() =>
      createWritingSuggestion({
        action: "refine",
        sceneContent: "원고",
        selectedText: "",
        characterNames: ["서윤", "도현"],
      }),
    ).toThrow("다듬을 문장을 먼저 선택해 주세요.");
  });

  test("returns a replacement for selected prose", async () => {
    const { createWritingSuggestion } = await import("./writing-assistant");

    const suggestion = createWritingSuggestion({
      action: "refine",
      sceneContent: "그는 슬펐다.",
      selectedText: "그는 슬펐다.",
      characterNames: ["서윤", "도현"],
    });

    expect(suggestion).toMatchObject({ action: "refine", kind: "replace" });
    expect(suggestion.content).not.toBe("그는 슬펐다.");
  });

  test("consistency checks return diagnostics, not text edits", async () => {
    const { createWritingSuggestion } = await import("./writing-assistant");

    const suggestion = createWritingSuggestion({
      action: "consistency",
      sceneContent: "원고",
      selectedText: "",
      characterNames: ["서윤", "도현"],
    });

    expect(suggestion.kind).toBe("diagnostic");
    expect(suggestion.content).toContain("일관성");
  });
});

