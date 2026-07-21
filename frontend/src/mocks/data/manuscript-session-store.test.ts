import { afterEach, describe, expect, test } from "vitest";

import type { ApiManuscript } from "@/app/infrastructure/api/contracts";
import {
  loadManuscriptSession,
  MANUSCRIPT_SESSION_STORAGE_KEY,
  saveManuscriptSession,
  type PersistedManuscriptSession,
} from "@/mocks/data/manuscript-session-store";

const manuscript: ApiManuscript = {
  id: "silver-garden-manuscript",
  projectId: "silver-garden",
  activeSceneId: "silver-garden-scene-1",
  scenes: [
    {
      id: "silver-garden-scene-1",
      title: "비가 그친 뒤의 정원",
      chapterNumber: 1,
      content: "첫째 줄",
      relatedCharacterIds: ["silver-garden-character-1"],
      relatedWorldEntryIds: ["silver-garden-world-1"],
    },
  ],
};

function createSession(content = manuscript.scenes[0].content): PersistedManuscriptSession {
  const nextManuscript = structuredClone(manuscript);
  nextManuscript.scenes[0].content = content;

  return {
    schemaVersion: 1,
    entries: [
      {
        projectId: "silver-garden",
        manuscript: nextManuscript,
        manuscriptRevision: 2,
        projectUpdatedAt: "2026-07-21T08:00:00.000Z",
      },
    ],
  };
}

describe("manuscript session storage", () => {
  afterEach(() => {
    window.sessionStorage.clear();
  });

  test.each([
    { name: "ordinary content", content: "첫째 줄" },
    { name: "empty content", content: "" },
    {
      name: "long multiline content",
      content: Array.from({ length: 300 }, (_, index) => `${index + 1}번째 줄`).join("\n"),
    },
  ])("round-trips $name without sharing caller-owned state", ({ content }) => {
    const session = createSession(content);

    saveManuscriptSession(window.sessionStorage, session);
    session.entries[0].manuscript.scenes[0].content = "호출자가 변경한 값";

    const loaded = loadManuscriptSession(window.sessionStorage);

    expect(loaded?.entries[0].manuscript.scenes[0].content).toBe(content);
    loaded!.entries[0].manuscript.scenes[0].content = "반환값 변경";
    expect(
      loadManuscriptSession(window.sessionStorage)?.entries[0].manuscript.scenes[0].content,
    ).toBe(content);
  });

  test.each([
    { name: "malformed JSON", value: "{" },
    {
      name: "an unknown schema version",
      value: JSON.stringify({ ...createSession(), schemaVersion: 2 }),
    },
    {
      name: "a zero revision",
      value: JSON.stringify({
        ...createSession(),
        entries: [{ ...createSession().entries[0], manuscriptRevision: 0 }],
      }),
    },
    {
      name: "a fractional revision",
      value: JSON.stringify({
        ...createSession(),
        entries: [{ ...createSession().entries[0], manuscriptRevision: 1.5 }],
      }),
    },
    {
      name: "a mismatched manuscript project",
      value: JSON.stringify({
        ...createSession(),
        entries: [
          {
            ...createSession().entries[0],
            manuscript: { ...createSession().entries[0].manuscript, projectId: "another-project" },
          },
        ],
      }),
    },
  ])("removes $name and recovers without throwing", ({ value }) => {
    window.sessionStorage.setItem(MANUSCRIPT_SESSION_STORAGE_KEY, value);

    expect(loadManuscriptSession(window.sessionStorage)).toBeUndefined();
    expect(window.sessionStorage.getItem(MANUSCRIPT_SESSION_STORAGE_KEY)).toBeNull();
  });
});
