import { useEffect, useState } from "react";
import { ArrowLeft, Check, Feather, FileText, Map, Users, WandSparkles } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";

import { useApp } from "@/app/state/app-provider";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { applyWritingSuggestion } from "@/features/apply-writing-suggestion";
import type { TextRange } from "@/modules/manuscript";
import { updateSceneContent } from "@/modules/manuscript";
import { ManuscriptEditor } from "@/modules/manuscript/ui/manuscript-editor";
import { SceneTree } from "@/modules/manuscript/ui/scene-tree";
import { StoryContextPanel } from "@/modules/story-bible/ui/story-context-panel";
import { WritingToolPanel } from "@/modules/writing-assistant/ui/writing-tool-panel";

type ContextMode = "manuscript" | "characters" | "world";

const contextTools: Array<{
  mode: ContextMode;
  label: string;
  icon: typeof FileText;
}> = [
  { mode: "manuscript", label: "원고 보기", icon: FileText },
  { mode: "characters", label: "인물 보기", icon: Users },
  { mode: "world", label: "세계관 보기", icon: Map },
];

export function WritingWorkspacePage() {
  const { projectId } = useParams();
  const { state, openProject, saveManuscript } = useApp();
  const [contextMode, setContextMode] = useState<ContextMode>("manuscript");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [selection, setSelection] = useState<TextRange | null>(null);
  const project = state.projects.find(({ id }) => id === projectId);
  const manuscript = state.manuscripts.find(
    ({ projectId: manuscriptProjectId }) => manuscriptProjectId === projectId,
  );
  const bible = state.storyBibles.find(
    ({ projectId: bibleProjectId }) => bibleProjectId === projectId,
  );
  const scene = manuscript?.scenes.find(({ id }) => id === manuscript.activeSceneId);

  useEffect(() => {
    if (projectId && project && state.lastProjectId !== projectId) {
      openProject(projectId);
    }
  }, [openProject, project, projectId, state.lastProjectId]);

  if (!project || !manuscript || !bible || !scene) {
    return <Navigate to="/" replace />;
  }

  const selectedRange = selection && selection.start !== selection.end ? selection : null;
  const selectedText = selectedRange
    ? scene.content.slice(selectedRange.start, selectedRange.end)
    : "";

  return (
    <div className="flex min-h-svh flex-col overflow-hidden bg-[#ede6dd]">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-card/95 px-3 shadow-sm lg:px-5">
        <div className="flex min-w-0 items-center gap-2.5">
          <Button variant="ghost" size="icon" asChild>
            <Link to="/" aria-label="작품 서재로 돌아가기">
              <ArrowLeft />
            </Link>
          </Button>
          <span className="grid size-8 place-items-center rounded-full bg-primary text-primary-foreground">
            <Feather className="size-3.5" />
          </span>
          <div className="min-w-0">
            <h1 className="truncate font-heading text-base font-semibold">{project.title}</h1>
            <p className="truncate text-[11px] text-muted-foreground">제1장 · {scene.title}</p>
          </div>
        </div>
        <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
          <Check className="size-3.5 text-primary" />
          <span className="hidden sm:inline">자동 저장됨</span>
        </span>
      </header>

      <div className="flex min-h-0 flex-1">
        <nav
          aria-label="집필 도메인"
          className="flex w-14 shrink-0 flex-col items-center gap-2 border-r border-border bg-sidebar py-3"
        >
          {contextTools.map((tool) => {
            const Icon = tool.icon;
            return (
              <Tooltip key={tool.mode}>
                <TooltipTrigger asChild>
                  <Button
                    aria-label={tool.label}
                    variant={contextMode === tool.mode ? "secondary" : "ghost"}
                    size="icon"
                    onClick={() => setContextMode(tool.mode)}
                    className={
                      contextMode === tool.mode ? "text-primary shadow-sm" : "text-muted-foreground"
                    }
                  >
                    <Icon />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">{tool.label}</TooltipContent>
              </Tooltip>
            );
          })}

          <div className="mt-auto">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  aria-label="AI 도구 열기"
                  variant={assistantOpen ? "default" : "outline"}
                  size="icon"
                  onClick={() => setAssistantOpen(true)}
                  className="shadow-sm"
                >
                  <WandSparkles />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">AI 도구 열기</TooltipContent>
            </Tooltip>
          </div>
        </nav>

        <aside className="hidden w-64 shrink-0 overflow-y-auto border-r border-border bg-sidebar/90 md:block">
          {contextMode === "manuscript" ? (
            <SceneTree manuscript={manuscript} />
          ) : (
            <StoryContextPanel bible={bible} mode={contextMode} />
          )}
        </aside>

        <main className="min-w-0 flex-1 overflow-y-auto p-3 sm:p-5 lg:p-6">
          <ManuscriptEditor
            scene={scene}
            onChange={(content) =>
              saveManuscript(updateSceneContent(manuscript, scene.id, content))
            }
            onSelectionChange={setSelection}
          />
        </main>

        {assistantOpen && (
          <div className="fixed inset-y-16 right-0 z-30 shadow-2xl xl:static xl:inset-auto xl:z-auto xl:shadow-none">
            <WritingToolPanel
              sceneContent={scene.content}
              selectedText={selectedText}
              characterNames={bible.characters.map(({ name }) => name)}
              onClose={() => setAssistantOpen(false)}
              onApply={(suggestion) => {
                const updated = applyWritingSuggestion({
                  manuscript,
                  sceneId: scene.id,
                  suggestion,
                  cursorPosition: selection?.end ?? scene.content.length,
                  selectedRange,
                });
                const updatedScene = updated.scenes.find(({ id }) => id === scene.id);
                saveManuscript(updated);
                if (updatedScene) {
                  setSelection({
                    start: updatedScene.content.length,
                    end: updatedScene.content.length,
                  });
                }
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
