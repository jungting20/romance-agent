import { describe, expect, test } from "vitest";

describe("StoryBible", () => {
  test("creates two distinct protagonists for a new project", async () => {
    const { createInitialStoryBible } = await import("./story-bible");

    const bible = createInitialStoryBible("project-1", ["서윤", "도현"]);

    expect(bible.characters).toEqual([
      expect.objectContaining({ id: "project-1-character-1", name: "서윤" }),
      expect.objectContaining({ id: "project-1-character-2", name: "도현" }),
    ]);
    expect(bible.worldEntries[0]).toMatchObject({
      id: "project-1-world-1",
      kind: "place",
    });
  });

  test("returns only context related to the active scene", async () => {
    const { createInitialStoryBible, selectSceneContext } = await import("./story-bible");
    const bible = createInitialStoryBible("project-1", ["서윤", "도현"]);

    const context = selectSceneContext(bible, {
      characterIds: ["project-1-character-2"],
      worldEntryIds: ["project-1-world-1"],
    });

    expect(context.characters.map(({ name }) => name)).toEqual(["도현"]);
    expect(context.worldEntries).toHaveLength(1);
  });
});
