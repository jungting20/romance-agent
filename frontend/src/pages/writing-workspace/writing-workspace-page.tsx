import { useState } from "react";
import {
  ArrowLeft,
  Check,
  CircleAlert,
  Feather,
  FileText,
  LoaderCircle,
  Map,
  Users,
  WandSparkles,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type { ProjectWorkspaceResponse } from "@/app/infrastructure/api/contracts";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { applyWritingSuggestion } from "@/features/apply-writing-suggestion";
import { ManuscriptConflictDialog } from "@/features/manuscript-conflict";
import {
  type ManuscriptAutosaveStatus,
  useManuscriptAutosave,
} from "@/features/manuscript-autosave";
import { useProjectWorkspaceQuery } from "@/features/project-persistence";
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
  const workspaceQuery = useProjectWorkspaceQuery(projectId ?? "");

  if (workspaceQuery.isPending) {
    return (
      <main className="grid min-h-svh place-items-center bg-[#ede6dd] p-6">
        <p role="status" className="rounded-2xl border border-border bg-card p-8 shadow-sm">
          작업 공간을 불러오는 중이에요.
        </p>
      </main>
    );
  }

  if (workspaceQuery.isError) {
    if (isProjectNotFound(workspaceQuery.error)) {
      return (
        <main className="grid min-h-svh place-items-center bg-[#ede6dd] p-6 text-center">
          <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
            <h1 className="font-heading text-2xl font-semibold">프로젝트를 찾을 수 없어요</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              작품 서재에서 다른 프로젝트를 선택해 주세요.
            </p>
            <Button asChild className="mt-5">
              <Link to="/" aria-label="작품 서재로 돌아가기">
                <ArrowLeft data-icon="inline-start" /> 작품 서재로 돌아가기
              </Link>
            </Button>
          </div>
        </main>
      );
    }

    return (
      <main className="grid min-h-svh place-items-center bg-[#ede6dd] p-6 text-center">
        <div
          role="alert"
          className="rounded-2xl border border-destructive/30 bg-card p-8 shadow-sm"
        >
          <p>작업 공간을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</p>
          <Button
            type="button"
            variant="outline"
            className="mt-4"
            onClick={() => void workspaceQuery.refetch()}
          >
            작업 공간 다시 불러오기
          </Button>
        </div>
      </main>
    );
  }

  return <LoadedWritingWorkspace workspace={workspaceQuery.data} />;
}

function LoadedWritingWorkspace({ workspace }: { workspace: ProjectWorkspaceResponse }) {
  const [contextMode, setContextMode] = useState<ContextMode>("manuscript");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [selection, setSelection] = useState<TextRange | null>(null);
  const { project, storyBible: bible } = workspace;
  const {
    draft,
    updateDraft,
    status,
    retry,
    conflictComparison,
    isConflictDialogOpen,
    isComparingConflict,
    isConflictCompareError,
    isResolvingConflict,
    isConflictResolutionError,
    keepLocal,
    retryKeepLocal,
    applyServer,
    retryConflictComparison,
    setConflictDialogVisibility,
    openConflictDialog,
  } = useManuscriptAutosave({
    manuscript: workspace.manuscript,
    manuscriptRevision: workspace.manuscriptRevision,
  });
  const scene = draft.scenes.find(({ id }) => id === draft.activeSceneId);

  if (!scene) {
    return (
      <main className="grid min-h-svh place-items-center bg-[#ede6dd] p-6">
        <p role="alert" className="rounded-2xl border border-destructive/30 bg-card p-8">
          현재 집필할 장면을 찾을 수 없어요.
        </p>
      </main>
    );
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
        <AutosaveIndicator status={status} onRetry={retry} onOpenConflict={openConflictDialog} />
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
            <SceneTree manuscript={draft} />
          ) : (
            <StoryContextPanel bible={bible} mode={contextMode} />
          )}
        </aside>

        <main className="min-w-0 flex-1 overflow-y-auto p-3 sm:p-5 lg:p-6">
          <ManuscriptEditor
            scene={scene}
            onChange={(content) => updateDraft(updateSceneContent(draft, scene.id, content))}
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
                  manuscript: draft,
                  sceneId: scene.id,
                  suggestion,
                  cursorPosition: selection?.end ?? scene.content.length,
                  selectedRange,
                });
                const updatedScene = updated.scenes.find(({ id }) => id === scene.id);
                updateDraft(updated);
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
      <ManuscriptConflictDialog
        open={isConflictDialogOpen}
        comparison={conflictComparison}
        isComparing={isComparingConflict}
        isResolving={isResolvingConflict}
        compareError={isConflictCompareError}
        resolutionError={isConflictResolutionError}
        onOpenChange={setConflictDialogVisibility}
        onKeepLocal={() => void keepLocal()}
        onApplyServer={applyServer}
        onRetryCompare={retryConflictComparison}
        onRetryKeepLocal={() => void retryKeepLocal()}
      />
    </div>
  );
}

function AutosaveIndicator({
  status,
  onRetry,
  onOpenConflict,
}: {
  status: ManuscriptAutosaveStatus;
  onRetry: () => void;
  onOpenConflict: () => void;
}) {
  if (status === "error") {
    return (
      <div role="alert" className="flex shrink-0 items-center gap-2 text-xs text-destructive">
        <CircleAlert className="size-3.5" />
        <span>저장 실패</span>
        <Button type="button" variant="ghost" size="sm" onClick={onRetry}>
          원고 저장 다시 시도
        </Button>
      </div>
    );
  }

  if (status === "conflict") {
    return (
      <div role="alert" className="flex shrink-0 items-center gap-1.5 text-xs text-destructive">
        <CircleAlert className="size-3.5" />
        <span>저장 충돌</span>
        <Button type="button" variant="ghost" size="sm" onClick={onOpenConflict}>
          충돌 해결 열기
        </Button>
      </div>
    );
  }

  const label = status === "editing" ? "편집 중" : status === "saving" ? "저장 중" : "자동 저장됨";

  return (
    <span
      role="status"
      aria-label={label}
      className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground"
    >
      {status === "saved" ? (
        <Check className="size-3.5 text-primary" />
      ) : (
        <LoaderCircle className={status === "saving" ? "size-3.5 animate-spin" : "size-3.5"} />
      )}
      <span className="hidden sm:inline">{label}</span>
    </span>
  );
}

function isProjectNotFound(error: Error): boolean {
  return (
    error instanceof ApiRequestError &&
    error.status === 404 &&
    error.error.code === "PROJECT_NOT_FOUND"
  );
}
