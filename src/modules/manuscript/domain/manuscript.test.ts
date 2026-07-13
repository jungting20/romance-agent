import { describe, expect, test } from "vitest";

describe("Manuscript", () => {
  test("creates a manuscript with an opening scene", async () => {
    const { createInitialManuscript } = await import("./manuscript");

    const manuscript = createInitialManuscript("project-1");

    expect(manuscript.activeSceneId).toBe("project-1-scene-1");
    expect(manuscript.scenes[0]).toMatchObject({
      id: "project-1-scene-1",
      title: "비가 그친 뒤의 정원",
      chapterNumber: 1,
    });
  });

  test("updates a scene without mutating the original manuscript", async () => {
    const { createInitialManuscript, updateSceneContent } = await import(
      "./manuscript"
    );
    const manuscript = createInitialManuscript("project-1");

    const updated = updateSceneContent(
      manuscript,
      "project-1-scene-1",
      "새로운 원고",
    );

    expect(updated.scenes[0]?.content).toBe("새로운 원고");
    expect(manuscript.scenes[0]?.content).not.toBe("새로운 원고");
  });

  test("inserts text at the selected cursor position", async () => {
    const { insertText } = await import("./manuscript");

    expect(insertText("그가 말했다.", 2, " 조용히")).toBe(
      "그가 조용히 말했다.",
    );
  });

  test("replaces a valid text range", async () => {
    const { replaceTextRange } = await import("./manuscript");

    expect(replaceTextRange("그는 웃었다.", { start: 3, end: 6 }, "미소 지었다"))
      .toBe("그는 미소 지었다.");
  });

  test("rejects a range outside the manuscript", async () => {
    const { replaceTextRange } = await import("./manuscript");

    expect(() =>
      replaceTextRange("짧은 글", { start: 0, end: 100 }, "교체"),
    ).toThrow("선택한 원고 범위가 올바르지 않습니다.");
  });
});

