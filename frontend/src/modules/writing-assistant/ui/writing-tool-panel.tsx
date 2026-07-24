import { CheckCircle2, MessageCircleMore, PenLine, Sparkles, WandSparkles, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  createWritingSuggestion,
  type Suggestion,
  type WritingAction,
} from "@/modules/writing-assistant";

interface WritingToolPanelProps {
  sceneContent: string;
  selectedText: string;
  characterNames: string[];
  onClose: () => void;
  onApply: (suggestion: Suggestion) => void;
}

const tools: Array<{
  action: WritingAction;
  label: string;
  description: string;
  icon: typeof Sparkles;
}> = [
  {
    action: "continue",
    label: "이어 쓰기",
    description: "현재 장면의 감정선을 유지해 다음 문단을 제안해요.",
    icon: Sparkles,
  },
  {
    action: "refine",
    label: "문장 다듬기",
    description: "선택한 문장을 감정을 보여주는 표현으로 바꿔요.",
    icon: PenLine,
  },
  {
    action: "dialogue",
    label: "대사 제안",
    description: "인물의 숨은 의도를 담은 대화를 제안해요.",
    icon: MessageCircleMore,
  },
  {
    action: "consistency",
    label: "일관성 검사",
    description: "인물, 장소, 감정선의 충돌을 확인해요.",
    icon: CheckCircle2,
  },
];

export function WritingToolPanel({
  sceneContent,
  selectedText,
  characterNames,
  onClose,
  onApply,
}: WritingToolPanelProps) {
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);

  function runTool(action: WritingAction) {
    setSuggestion(
      createWritingSuggestion({
        action,
        sceneContent,
        selectedText,
        characterNames,
      }),
    );
  }

  return (
    <aside className="flex h-full w-full min-w-0 max-w-full flex-col border-l border-border bg-card">
      <div className="flex h-14 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-full bg-primary text-primary-foreground">
            <WandSparkles className="size-4" />
          </span>
          <div>
            <h2 className="text-sm font-semibold">AI 집필 도구</h2>
            <p className="text-[10px] text-muted-foreground">요청할 때만 원고를 읽어요</p>
          </div>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="AI 도구 닫기">
          <X />
        </Button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        <div className="space-y-2">
          {tools.map((tool) => {
            const Icon = tool.icon;
            const disabled = tool.action === "refine" && !selectedText;
            return (
              <button
                key={tool.action}
                type="button"
                aria-label={tool.label}
                disabled={disabled}
                onClick={() => runTool(tool.action)}
                className="group flex w-full gap-3 rounded-xl border border-border bg-background/55 p-3 text-left transition hover:border-primary/30 hover:bg-secondary/55 disabled:cursor-not-allowed disabled:opacity-45"
              >
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-secondary text-primary">
                  <Icon className="size-4" />
                </span>
                <span>
                  <span className="block text-xs font-semibold">{tool.label}</span>
                  <span className="mt-1 block text-[10px] leading-4 text-muted-foreground">
                    {tool.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        {suggestion && (
          <Card className="gap-3 border-primary/25 bg-secondary/35 py-4 shadow-none">
            <CardContent className="px-4">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div>
                  <Badge className="mb-2">Muse 제안</Badge>
                  <h3 className="font-heading text-base font-semibold">{suggestion.title}</h3>
                </div>
              </div>
              <p className="whitespace-pre-wrap text-xs leading-6 text-foreground/80">
                {suggestion.content}
              </p>
              <div className="mt-4 flex gap-2">
                {suggestion.kind !== "diagnostic" && (
                  <Button
                    size="sm"
                    onClick={() => {
                      onApply(suggestion);
                      setSuggestion(null);
                    }}
                  >
                    원고에 적용
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => setSuggestion(null)}>
                  닫기
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </aside>
  );
}
