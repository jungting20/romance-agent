import {
  insertText,
  type Manuscript,
  replaceTextRange,
  type TextRange,
  updateSceneContent,
} from "@/modules/manuscript";
import type { Suggestion } from "@/modules/writing-assistant";

export interface ApplyWritingSuggestionInput {
  manuscript: Manuscript;
  sceneId: string;
  suggestion: Suggestion;
  cursorPosition: number;
  selectedRange: TextRange | null;
}

export function applyWritingSuggestion({
  manuscript,
  sceneId,
  suggestion,
  cursorPosition,
  selectedRange,
}: ApplyWritingSuggestionInput): Manuscript {
  if (suggestion.kind === "diagnostic") {
    return manuscript;
  }

  const scene = manuscript.scenes.find(({ id }) => id === sceneId);

  if (!scene) {
    throw new Error("원고 장면을 찾을 수 없습니다.");
  }

  const content =
    suggestion.kind === "insert"
      ? insertText(scene.content, cursorPosition, suggestion.content)
      : replaceTextRange(scene.content, selectedRange ?? invalidSelection(), suggestion.content);

  return updateSceneContent(manuscript, sceneId, content);
}

function invalidSelection(): never {
  throw new Error("교체할 원고 범위를 선택해 주세요.");
}
