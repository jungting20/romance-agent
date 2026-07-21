import { describe, expect, test } from "vitest";

import {
  addScene,
  createInitialManuscript,
  updateSceneContent,
  type Manuscript,
} from "@/modules/manuscript";

import { findLocalSceneAdditions, mergeLocalSceneAdditions } from "./manuscript-structure-conflict";

describe("manuscript structure conflict", () => {
  test("finds scenes added after the acknowledged manuscript", () => {
    const base = createInitialManuscript("project-1");
    const local = addScene(addScene(base, "local-2"), "local-3");

    expect(findLocalSceneAdditions(base, local).map(({ id }) => id)).toEqual([
      "local-2",
      "local-3",
    ]);
  });

  test("appends local-only scenes to the latest server manuscript", () => {
    const base = createInitialManuscript("project-1");
    const local = updateSceneContent(addScene(base, "local-2"), "local-2", "새 장면 본문");
    const server = updateSceneContent(base, base.activeSceneId, "서버 최신 본문");

    const merged = mergeLocalSceneAdditions(base, local, server);

    expect(merged.scenes[0]?.content).toBe("서버 최신 본문");
    expect(merged.scenes[1]?.id).toBe("local-2");
    expect(merged.scenes[1]?.content).toBe("새 장면 본문");
    expect(merged.activeSceneId).toBe("local-2");
  });

  test("keeps the server active scene when the local active scene is absent after merging", () => {
    const base = createInitialManuscript("project-1");
    const local = {
      ...addScene(base, "local-2"),
      activeSceneId: "missing-scene",
    };

    const merged = mergeLocalSceneAdditions(base, local, base);

    expect(merged.activeSceneId).toBe(base.activeSceneId);
  });

  test("refuses automatic merge without a local-only scene", () => {
    const base = createInitialManuscript("project-1");

    expect(() => mergeLocalSceneAdditions(base, base, base)).toThrow("병합할 새 장면이 없습니다.");
  });

  test("refuses automatic merge when the local draft also changes a base scene", () => {
    const base = createInitialManuscript("project-1");
    const local = updateSceneContent(
      addScene(base, "local-2"),
      base.activeSceneId,
      "로컬 기존 장면 변경",
    );

    expect(() => mergeLocalSceneAdditions(base, local, base)).toThrow(
      "기존 장면의 로컬 변경과 새 장면을 동시에 자동 병합할 수 없습니다.",
    );
  });

  test("refuses automatic merge when the local draft removes a base scene", () => {
    const base = createInitialManuscript("project-1");
    const local: Manuscript = {
      ...addScene(base, "local-2"),
      scenes: [addScene(base, "local-2").scenes[1]!],
    };

    expect(() => mergeLocalSceneAdditions(base, local, base)).toThrow(
      "기존 장면의 로컬 변경과 새 장면을 동시에 자동 병합할 수 없습니다.",
    );
  });

  test("refuses automatic merge when a local-only scene ID exists on the server", () => {
    const base = createInitialManuscript("project-1");
    const local = addScene(base, "scene-2");
    const server = addScene(base, "scene-2");

    expect(() => mergeLocalSceneAdditions(base, local, server)).toThrow(
      "서버 원고와 새 장면 식별자가 충돌합니다.",
    );
  });

  test("refuses automatic merge when a local-only chapter number exists on the server", () => {
    const base = createInitialManuscript("project-1");
    const local = addScene(base, "local-2");
    const server = addScene(base, "server-2");

    expect(() => mergeLocalSceneAdditions(base, local, server)).toThrow(
      "서버 원고와 새 장 번호가 충돌합니다.",
    );
  });
});
