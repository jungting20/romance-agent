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
    const { createInitialManuscript, updateSceneContent } = await import("./manuscript");
    const manuscript = createInitialManuscript("project-1");

    const updated = updateSceneContent(manuscript, "project-1-scene-1", "새로운 원고");

    expect(updated.scenes[0]?.content).toBe("새로운 원고");
    expect(manuscript.scenes[0]?.content).not.toBe("새로운 원고");
  });

  test("normalizes and updates only one existing scene title", async () => {
    const { addScene, createInitialManuscript, updateSceneTitle } = await import("./manuscript");
    const manuscript = addScene(createInitialManuscript("project-1"), "scene-2");
    const originalFirst = manuscript.scenes[0];
    const originalSecond = manuscript.scenes[1];

    const updated = updateSceneTitle(manuscript, "scene-2", "  남겨진 편지  ");

    expect(updated.scenes[1]).toEqual({ ...originalSecond, title: "남겨진 편지" });
    expect(updated.scenes[0]).toBe(originalFirst);
    expect(updated.activeSceneId).toBe(manuscript.activeSceneId);
    expect(manuscript.scenes[1]).toBe(originalSecond);
  });

  test("returns the same manuscript when the normalized title is unchanged", async () => {
    const { createInitialManuscript, updateSceneTitle } = await import("./manuscript");
    const manuscript = createInitialManuscript("project-1");
    const title = manuscript.scenes[0]!.title;

    expect(updateSceneTitle(manuscript, manuscript.activeSceneId, `  ${title}  `)).toBe(manuscript);
  });

  test.each(["", "   "])("rejects a blank scene title %j", async (title) => {
    const { createInitialManuscript, updateSceneTitle } = await import("./manuscript");
    const manuscript = createInitialManuscript("project-1");

    expect(() => updateSceneTitle(manuscript, manuscript.activeSceneId, title)).toThrow(
      "장면 제목을 입력해 주세요.",
    );
    expect(manuscript.scenes[0]!.title).toBe("비가 그친 뒤의 정원");
  });

  test("rejects a title update for a missing scene", async () => {
    const { createInitialManuscript, updateSceneTitle } = await import("./manuscript");

    expect(() => updateSceneTitle(createInitialManuscript("project-1"), "missing", "제목")).toThrow(
      "원고 장면을 찾을 수 없습니다.",
    );
  });

  test("adds and activates one empty scene after the highest chapter number", async () => {
    const { addScene, createInitialManuscript } = await import("./manuscript");
    const manuscript = createInitialManuscript("project-1");

    const updated = addScene(manuscript, "project-1-scene-2");

    expect(updated.scenes).toHaveLength(2);
    expect(updated.scenes[1]).toEqual({
      id: "project-1-scene-2",
      title: "제목 없는 장면",
      chapterNumber: 2,
      content: "",
      relatedCharacterIds: [],
      relatedWorldEntryIds: [],
    });
    expect(updated.activeSceneId).toBe("project-1-scene-2");
    expect(manuscript.scenes).toHaveLength(1);
  });

  test("numbers from the maximum chapter rather than the array length", async () => {
    const { addScene, createInitialManuscript } = await import("./manuscript");
    const manuscript = createInitialManuscript("project-1");
    const sparse = {
      ...manuscript,
      scenes: [{ ...manuscript.scenes[0]!, chapterNumber: 4 }],
    };

    expect(addScene(sparse, "scene-5").scenes[1]?.chapterNumber).toBe(5);
  });

  test.each(["", "project-1-scene-1"])("rejects invalid new scene id %j", async (sceneId) => {
    const { addScene, createInitialManuscript } = await import("./manuscript");

    expect(() => addScene(createInitialManuscript("project-1"), sceneId)).toThrow();
  });

  test("selects an existing scene without changing scene content", async () => {
    const { addScene, createInitialManuscript, selectScene } = await import("./manuscript");
    const manuscript = addScene(createInitialManuscript("project-1"), "scene-2");

    const selected = selectScene(manuscript, "project-1-scene-1");

    expect(selected.activeSceneId).toBe("project-1-scene-1");
    expect(selected.scenes).toBe(manuscript.scenes);
    expect(manuscript.activeSceneId).toBe("scene-2");
  });

  test("rejects selecting a missing scene", async () => {
    const { createInitialManuscript, selectScene } = await import("./manuscript");

    expect(() => selectScene(createInitialManuscript("project-1"), "missing-scene")).toThrow(
      "원고 장면을 찾을 수 없습니다.",
    );
  });

  test("inserts text at the selected cursor position", async () => {
    const { insertText } = await import("./manuscript");

    expect(insertText("그가 말했다.", 2, " 조용히")).toBe("그가 조용히 말했다.");
  });

  test("replaces a valid text range", async () => {
    const { replaceTextRange } = await import("./manuscript");

    expect(replaceTextRange("그는 웃었다.", { start: 3, end: 6 }, "미소 지었다")).toBe(
      "그는 미소 지었다.",
    );
  });

  test("rejects a range outside the manuscript", async () => {
    const { replaceTextRange } = await import("./manuscript");

    expect(() => replaceTextRange("짧은 글", { start: 0, end: 100 }, "교체")).toThrow(
      "선택한 원고 범위가 올바르지 않습니다.",
    );
  });
});
