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

  test("trims only the required character name and accepts empty optional strings", async () => {
    const { emptyCharacterDraft, validateCharacterDraft } = await import("./story-bible");
    const draft = { ...emptyCharacterDraft, name: "  민서  ", age: "", role: "" };

    expect(validateCharacterDraft(draft)).toEqual({
      value: { ...emptyCharacterDraft, name: "민서", age: "", role: "" },
      errors: {},
    });
    expect(draft.name).toBe("  민서  ");
  });

  test("rejects a character name that is blank after trimming", async () => {
    const { emptyCharacterDraft, validateCharacterDraft } = await import("./story-bible");

    expect(validateCharacterDraft({ ...emptyCharacterDraft, name: " \n " })).toEqual({
      errors: { name: "이름을 입력해 주세요." },
    });
  });

  test("trims a valid world-entry draft without mutating the caller value", async () => {
    const { validateWorldEntryDraft } = await import("./story-bible");
    const draft = {
      kind: "rule" as const,
      title: "  왕실의 서약  ",
      description: "  어길 수 없다.  ",
    };

    expect(validateWorldEntryDraft(draft)).toEqual({
      value: { kind: "rule", title: "왕실의 서약", description: "어길 수 없다." },
      errors: {},
    });
    expect(draft).toEqual({
      kind: "rule",
      title: "  왕실의 서약  ",
      description: "  어길 수 없다.  ",
    });
  });

  test("reports every blank normalized required field in one pass", async () => {
    const { validateWorldEntryDraft } = await import("./story-bible");

    expect(validateWorldEntryDraft({ kind: "place", title: " \n ", description: "\t" })).toEqual({
      errors: {
        title: "제목을 입력해 주세요.",
        description: "설명을 입력해 주세요.",
      },
    });
  });
});
