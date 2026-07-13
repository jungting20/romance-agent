import { describe, expect, test } from "vitest";

describe("application state", () => {
  test("starts with a coherent sample workspace", async () => {
    const { createSeedSnapshot } = await import("./app-state");

    const snapshot = createSeedSnapshot();

    expect(snapshot.version).toBe(1);
    expect(snapshot.projects).toHaveLength(1);
    expect(snapshot.manuscripts[0]?.projectId).toBe(snapshot.projects[0]?.id);
    expect(snapshot.lastProjectId).toBe(snapshot.projects[0]?.id);
  });

  test("adds every aggregate created by the project workflow", async () => {
    const { appReducer, createEmptySnapshot } = await import("./app-state");
    const { createProjectFromTrope } = await import("@/features/create-project");
    const workspace = createProjectFromTrope(
      {
        title: "새 작품",
        logline: "계약이 사랑으로 바뀐다.",
        tropeId: "contract-romance",
        protagonistNames: ["하린", "정우"],
      },
      {
        projectId: "project-new",
        conceptId: "concept-new",
        now: "2026-07-13T06:00:00.000Z",
      },
    );

    const state = appReducer(createEmptySnapshot(), {
      type: "workspace/created",
      workspace,
    });

    expect(state.projects).toHaveLength(1);
    expect(state.concepts).toHaveLength(1);
    expect(state.storyBibles).toHaveLength(1);
    expect(state.manuscripts).toHaveLength(1);
    expect(state.lastProjectId).toBe("project-new");
  });

  test("opens a project without changing domain aggregates", async () => {
    const { appReducer, createSeedSnapshot } = await import("./app-state");
    const snapshot = createSeedSnapshot();

    const state = appReducer(snapshot, {
      type: "workspace/opened",
      projectId: "another-project",
    });

    expect(state.lastProjectId).toBe("another-project");
    expect(state.projects).toBe(snapshot.projects);
  });

  test("replaces a saved manuscript and updates its project timestamp", async () => {
    const { appReducer, createSeedSnapshot } = await import("./app-state");
    const { updateSceneContent } = await import("@/modules/manuscript");
    const snapshot = createSeedSnapshot();
    const manuscript = updateSceneContent(
      snapshot.manuscripts[0]!,
      "silver-garden-scene-1",
      "수정된 원고",
    );

    const state = appReducer(snapshot, {
      type: "manuscript/saved",
      manuscript,
      updatedAt: "2026-07-13T08:00:00.000Z",
    });

    expect(state.manuscripts[0]?.scenes[0]?.content).toBe("수정된 원고");
    expect(state.projects[0]?.updatedAt).toBe("2026-07-13T08:00:00.000Z");
  });
});
