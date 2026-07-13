import { describe, expect, test } from "vitest";

describe("Project", () => {
  test("creates a project with normalized text", async () => {
    const { createProject } = await import("./project");

    const project = createProject({
      id: "project-1",
      title: "  은빛 정원의 약속  ",
      logline: "  헤어진 연인이 오래된 온실에서 다시 만난다.  ",
      tropeId: "reunion",
      updatedAt: "2026-07-13T05:00:00.000Z",
    });

    expect(project).toEqual({
      id: "project-1",
      title: "은빛 정원의 약속",
      logline: "헤어진 연인이 오래된 온실에서 다시 만난다.",
      tropeId: "reunion",
      updatedAt: "2026-07-13T05:00:00.000Z",
    });
  });

  test("rejects an empty title", async () => {
    const { createProject } = await import("./project");

    expect(() =>
      createProject({
        id: "project-1",
        title: "   ",
        logline: "로그라인",
        tropeId: "reunion",
        updatedAt: "2026-07-13T05:00:00.000Z",
      }),
    ).toThrow("작품 제목을 입력해 주세요.");
  });

  test("sorts projects by the most recently updated", async () => {
    const { sortProjectsByRecent } = await import("./project");
    const older = {
      id: "older",
      title: "오래된 작품",
      logline: "",
      tropeId: "rivals",
      updatedAt: "2026-07-12T00:00:00.000Z",
    };
    const newer = {
      ...older,
      id: "newer",
      title: "새 작품",
      updatedAt: "2026-07-13T00:00:00.000Z",
    };

    expect(sortProjectsByRecent([older, newer]).map(({ id }) => id)).toEqual(["newer", "older"]);
  });
});
