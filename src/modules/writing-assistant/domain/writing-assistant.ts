export type WritingAction = "continue" | "refine" | "dialogue" | "consistency";

export interface WritingRequest {
  action: WritingAction;
  sceneContent: string;
  selectedText: string;
  characterNames: string[];
}

export interface Suggestion {
  id: string;
  action: WritingAction;
  kind: "insert" | "replace" | "diagnostic";
  title: string;
  content: string;
}

export function createWritingSuggestion(request: WritingRequest): Suggestion {
  const [first = "주인공", second = "상대"] = request.characterNames;

  switch (request.action) {
    case "continue":
      return {
        id: "suggestion-continue",
        action: request.action,
        kind: "insert",
        title: "다음 문단 제안",
        content: `\n\n${second}은 대답 대신 창가에 맺힌 빗물을 바라보았다. ${first}은 그 짧은 침묵 속에서 오래전 듣지 못했던 말의 모양을 보았다.`,
      };
    case "refine":
      if (!request.selectedText.trim()) {
        throw new Error("다듬을 문장을 먼저 선택해 주세요.");
      }

      return {
        id: "suggestion-refine",
        action: request.action,
        kind: "replace",
        title: "감정을 보여주는 문장",
        content: `${request.selectedText.replace(/[.]$/, "")}—말끝에 남은 감정만은 미처 감추지 못한 채.`,
      };
    case "dialogue":
      return {
        id: "suggestion-dialogue",
        action: request.action,
        kind: "insert",
        title: "숨은 의도가 있는 대사",
        content: `\n\n“지금 와서 그 말을 믿으라는 거야?” ${first}이 물었다.\n“믿어 달라는 게 아니야.” ${second}은 시선을 피하지 않았다. “이번에는 듣기만 해 줘.”`,
      };
    case "consistency":
      return {
        id: "suggestion-consistency",
        action: request.action,
        kind: "diagnostic",
        title: "장면 일관성 검사",
        content:
          "일관성 문제를 찾지 못했습니다. 인물, 장소, 시간 흐름이 맞고 감정선은 이전의 거리감을 유지하고 있습니다.",
      };
  }
}
