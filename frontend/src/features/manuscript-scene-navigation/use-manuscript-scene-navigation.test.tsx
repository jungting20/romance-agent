import { act, renderHook } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { addScene, createInitialManuscript, type Manuscript } from "@/modules/manuscript";

import { useManuscriptSceneNavigation } from "./use-manuscript-scene-navigation";

type DraftUpdate = Manuscript | ((current: Manuscript) => Manuscript);

describe("useManuscriptSceneNavigation", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "requestAnimationFrame",
      vi.fn((callback: FrameRequestCallback) => {
        callback(0);
        return 1;
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("새 장면을 하나 추가하고 모바일 문맥 패널을 닫은 뒤 편집기로 이동한다", () => {
    const closeContext = vi.fn();
    const createSceneId = vi.fn(() => "scene-3");
    const initialManuscript = addScene(createInitialManuscript("project-1"), "scene-2");
    const editor = document.createElement("textarea");
    const focusEditor = vi.spyOn(editor, "focus");

    const { result } = renderHook(() => {
      const [manuscript, setManuscript] = useState(initialManuscript);
      const navigation = useManuscriptSceneNavigation({
        manuscript,
        updateDraft: setManuscript,
        contextIsInline: false,
        onCloseContext: closeContext,
        createSceneId,
      });

      return { manuscript, navigation };
    });

    act(() => {
      result.current.navigation.editorRef.current = editor;
      result.current.navigation.setSelection({ start: 1, end: 3 });
    });

    act(() => result.current.navigation.addNewScene());

    expect(result.current.manuscript.scenes).toHaveLength(3);
    expect(result.current.navigation.activeScene?.id).toBe("scene-3");
    expect(result.current.navigation.selection).toBeNull();
    expect(result.current.navigation.announcement).toBe("3장 장면을 추가했어요");
    expect(createSceneId).toHaveBeenCalledOnce();
    expect(createSceneId).toHaveBeenCalledWith(initialManuscript);
    expect(closeContext).toHaveBeenCalledOnce();
    expect(requestAnimationFrame).toHaveBeenCalledOnce();
    expect(focusEditor).toHaveBeenCalledOnce();
  });

  test("기존 장면을 선택하면 장면 객체를 보존하고 인라인 문맥 패널은 닫지 않는다", () => {
    const closeContext = vi.fn();
    const initialManuscript = addScene(createInitialManuscript("project-1"), "scene-2");
    const [firstScene, secondScene] = initialManuscript.scenes;

    const { result } = renderHook(() => {
      const [manuscript, setManuscript] = useState(initialManuscript);
      const navigation = useManuscriptSceneNavigation({
        manuscript,
        updateDraft: setManuscript,
        contextIsInline: true,
        onCloseContext: closeContext,
      });

      return { manuscript, navigation };
    });

    act(() => result.current.navigation.setSelection({ start: 0, end: 2 }));
    act(() => result.current.navigation.activateScene(firstScene.id));

    expect(result.current.navigation.activeScene).toBe(firstScene);
    expect(result.current.manuscript.scenes).toEqual([firstScene, secondScene]);
    expect(result.current.manuscript.scenes[0]).toBe(firstScene);
    expect(result.current.manuscript.scenes[1]).toBe(secondScene);
    expect(result.current.navigation.selection).toBeNull();
    expect(closeContext).not.toHaveBeenCalled();
  });

  test("업데이터가 지연되거나 재시도되어도 장면 ID는 한 번만 생성한다", () => {
    const initialManuscript = addScene(createInitialManuscript("project-1"), "scene-2");
    const createSceneId = vi.fn(() => "scene-3");
    let capturedUpdater: ((current: Manuscript) => Manuscript) | undefined;
    const updateDraft = vi.fn((update: DraftUpdate) => {
      if (typeof update === "function") capturedUpdater = update;
    });

    const { result } = renderHook(() =>
      useManuscriptSceneNavigation({
        manuscript: initialManuscript,
        updateDraft,
        contextIsInline: true,
        onCloseContext: vi.fn(),
        createSceneId,
      }),
    );

    act(() => result.current.addNewScene());

    expect(createSceneId).toHaveBeenCalledOnce();
    expect(result.current.announcement).toBe("3장 장면을 추가했어요");
    expect(capturedUpdater).toBeTypeOf("function");
    if (!capturedUpdater) throw new Error("기대한 원고 업데이터가 없습니다.");

    const firstResult = capturedUpdater(initialManuscript);
    const retriedResult = capturedUpdater(initialManuscript);

    expect(createSceneId).toHaveBeenCalledOnce();
    expect(firstResult).toEqual(retriedResult);
    expect(firstResult.scenes).toHaveLength(3);
    expect(firstResult.activeSceneId).toBe("scene-3");
  });
});
