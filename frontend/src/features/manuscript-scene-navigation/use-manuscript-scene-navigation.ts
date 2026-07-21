import { useRef, useState } from "react";

import { addScene, selectScene, type Manuscript, type TextRange } from "@/modules/manuscript";

type DraftUpdate = Manuscript | ((current: Manuscript) => Manuscript);

interface UseManuscriptSceneNavigationOptions {
  manuscript: Manuscript;
  updateDraft: (update: DraftUpdate) => void;
  contextIsInline: boolean;
  onCloseContext: () => void;
  createSceneId?: (manuscript: Manuscript) => string;
}

export function useManuscriptSceneNavigation({
  manuscript,
  updateDraft,
  contextIsInline,
  onCloseContext,
  createSceneId = (current) => `${current.projectId}-scene-${crypto.randomUUID()}`,
}: UseManuscriptSceneNavigationOptions) {
  const [selection, setSelection] = useState<TextRange | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const activeScene = manuscript.scenes.find(({ id }) => id === manuscript.activeSceneId);

  const finishNavigation = () => {
    setSelection(null);
    if (!contextIsInline) onCloseContext();
    requestAnimationFrame(() => editorRef.current?.focus());
  };

  const addNewScene = () => {
    const sceneId = createSceneId(manuscript);
    const chapterNumber = Math.max(...manuscript.scenes.map((scene) => scene.chapterNumber)) + 1;
    updateDraft((current) => addScene(current, sceneId));
    setAnnouncement(`${chapterNumber}장 장면을 추가했어요`);
    finishNavigation();
  };

  const activateScene = (sceneId: string) => {
    updateDraft((current) => selectScene(current, sceneId));
    finishNavigation();
  };

  return {
    activeScene,
    selection,
    setSelection,
    editorRef,
    announcement,
    addNewScene,
    activateScene,
  };
}
