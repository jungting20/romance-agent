import { type Ref, useEffect, useRef, useState } from "react";
import { Link, useBlocker, useNavigate, useParams, useSearch } from "@tanstack/react-router";
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

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type { ProjectWorkspaceResponse } from "@/app/infrastructure/api/contracts";
import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { applyWritingSuggestion } from "@/features/apply-writing-suggestion";
import {
  CharacterCardEditorSheet,
  CharacterDiscardDialog,
  useCharacterCardEditor,
} from "@/features/character-card-editor";
import {
  useWorldEntryEditor,
  WorldDiscardDialog,
  WorldEditorInitializingSheet,
  WorldEditorSheet,
} from "@/features/edit-world-entries";
import { ManuscriptConflictDialog } from "@/features/manuscript-conflict";
import {
  type ManuscriptAutosaveStatus,
  useManuscriptAutosave,
} from "@/features/manuscript-autosave";
import { useManuscriptSceneNavigation } from "@/features/manuscript-scene-navigation";
import { useProjectWorkspaceQuery } from "@/features/project-persistence";
import { useMediaQuery } from "@/hooks/use-media-query";
import { updateSceneContent, updateSceneTitle } from "@/modules/manuscript";
import { ManuscriptEditor } from "@/modules/manuscript/ui/manuscript-editor";
import { SceneTree } from "@/modules/manuscript/ui/scene-tree";
import { StoryContextPanel } from "@/modules/story-bible/ui/story-context-panel";
import { WritingToolPanel } from "@/modules/writing-assistant/ui/writing-tool-panel";

import {
  type ContextMode,
  isTabOnlyWorkspaceNavigation,
  parseCharacterId,
} from "./writing-workspace-tabs";

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
  const { projectId } = useParams({ from: "/projects/$projectId/write" });
  const search = useSearch({ from: "/projects/$projectId/write" });
  const { tab, panel } = search;
  const characterId = parseCharacterId(search.characterId);
  const navigate = useNavigate({ from: "/projects/$projectId/write" });
  const contextMode: ContextMode = tab ?? "manuscript";
  const workspaceQuery = useProjectWorkspaceQuery(projectId);

  useEffect(() => {
    if (tab !== "manuscript") return;

    void navigate({
      replace: true,
      search: (previous) => {
        const { tab: _tab, ...rest } = previous;
        return rest;
      },
    });
  }, [navigate, tab]);

  useEffect(() => {
    if (panel !== null) return;
    void navigate({
      replace: true,
      search: (previous) => {
        const { panel: _panel, ...rest } = previous;
        return rest;
      },
    });
  }, [navigate, panel]);

  useEffect(() => {
    if (panel !== "world-editor" || tab === "world") return;
    void navigate({
      replace: true,
      search: (previous) => ({
        ...previous,
        tab: "world",
        panel: "world-editor",
      }),
    });
  }, [navigate, panel, tab]);

  useEffect(() => {
    if (panel !== "character-editor" || tab === "characters") return;
    void navigate({
      replace: true,
      search: (previous) => ({
        ...previous,
        tab: "characters",
        panel: "character-editor",
      }),
    });
  }, [navigate, panel, tab]);

  useEffect(() => {
    if (panel === "character-editor" || search.characterId === undefined) return;
    void navigate({
      replace: true,
      search: (previous) => {
        const { characterId: _characterId, ...rest } = previous;
        return rest;
      },
    });
  }, [navigate, panel, search.characterId]);

  useEffect(() => {
    if (
      panel !== "character-editor" ||
      search.characterId === undefined ||
      characterId !== undefined
    ) {
      return;
    }
    void navigate({
      replace: true,
      search: (previous) => {
        const { characterId: _characterId, ...rest } = previous;
        return rest;
      },
    });
  }, [characterId, navigate, panel, search.characterId]);

  function handleContextModeChange(mode: ContextMode) {
    void navigate({
      search: (previous) => {
        const { tab: _tab, ...searchWithEditor } = previous;
        let search = searchWithEditor;
        if (panel === "character-editor") {
          const {
            panel: _panel,
            characterId: _characterId,
            ...withoutCharacterEditor
          } = searchWithEditor;
          search = withoutCharacterEditor;
        }
        return mode === "manuscript" ? search : { ...search, tab: mode };
      },
    });
  }

  if (workspaceQuery.isPending) {
    return (
      <main role="status" className="flex h-svh min-h-0 flex-col overflow-hidden bg-[#ede6dd]">
        <span className="sr-only">작업 공간을 불러오는 중이에요.</span>
        <header aria-hidden="true" className="flex h-16 items-center gap-3 border-b bg-card px-5">
          <Skeleton className="size-8 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-24" />
          </div>
        </header>
        <div aria-hidden="true" className="flex min-h-0 flex-1">
          <div className="w-14 border-r bg-sidebar p-3">
            <Skeleton className="h-32 w-full" />
          </div>
          <div className="hidden w-64 border-r bg-sidebar/90 p-4 md:block">
            <Skeleton className="h-full w-full" />
          </div>
          <div className="flex-1 p-6">
            <Skeleton className="mx-auto h-full max-w-3xl bg-card" />
          </div>
        </div>
      </main>
    );
  }

  if (workspaceQuery.isError) {
    if (isProjectNotFound(workspaceQuery.error)) {
      return (
        <main className="grid min-h-svh place-items-center bg-[#ede6dd] p-6 text-center">
          <Alert role={undefined} className="max-w-md p-8 shadow-sm">
            <AlertTitle>
              <h1 className="font-heading text-2xl font-semibold">프로젝트를 찾을 수 없어요</h1>
            </AlertTitle>
            <AlertDescription className="mt-2">
              작품 서재에서 다른 프로젝트를 선택해 주세요.
            </AlertDescription>
            <AlertAction className="static mt-5">
              <Button asChild>
                <Link to="/" aria-label="작품 서재로 돌아가기">
                  <ArrowLeft data-icon="inline-start" /> 작품 서재로 돌아가기
                </Link>
              </Button>
            </AlertAction>
          </Alert>
        </main>
      );
    }

    return (
      <main className="grid min-h-svh place-items-center bg-[#ede6dd] p-6 text-center">
        <Alert variant="destructive" className="max-w-md p-8 shadow-sm">
          <AlertTitle>작업 공간을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</AlertTitle>
          <AlertAction className="static mt-4">
            <Button type="button" variant="outline" onClick={() => void workspaceQuery.refetch()}>
              작업 공간 다시 불러오기
            </Button>
          </AlertAction>
        </Alert>
      </main>
    );
  }

  return (
    <LoadedWritingWorkspace
      workspace={workspaceQuery.data}
      contextMode={contextMode}
      worldEditorOpen={panel === "world-editor" && contextMode === "world"}
      characterEditorOpen={panel === "character-editor" && contextMode === "characters"}
      characterId={characterId}
      onContextModeChange={handleContextModeChange}
      onWorldEditorOpen={() => {
        void navigate({
          search: (previous) => ({
            ...previous,
            tab: "world",
            panel: "world-editor",
          }),
        });
      }}
      onWorldEditorClose={(replace = false) => {
        void navigate({
          replace,
          search: (previous) => {
            const { panel: _panel, ...rest } = previous;
            return { ...rest, tab: "world" };
          },
        });
      }}
      onCharacterEditorOpen={(nextCharacterId) => {
        void navigate({
          search: (previous) => {
            const { characterId: _characterId, ...rest } = previous;
            return {
              ...rest,
              tab: "characters",
              panel: "character-editor",
              ...(nextCharacterId ? { characterId: nextCharacterId } : {}),
            };
          },
        });
      }}
      onCharacterEditorClose={(replace = false) => {
        void navigate({
          replace,
          search: (previous) => {
            const { panel: _panel, characterId: _characterId, ...rest } = previous;
            return { ...rest, tab: "characters" };
          },
        });
      }}
    />
  );
}

function LoadedWritingWorkspace({
  workspace,
  contextMode,
  worldEditorOpen,
  characterEditorOpen,
  characterId,
  onContextModeChange,
  onWorldEditorOpen,
  onWorldEditorClose,
  onCharacterEditorOpen,
  onCharacterEditorClose,
}: {
  workspace: ProjectWorkspaceResponse;
  contextMode: ContextMode;
  worldEditorOpen: boolean;
  characterEditorOpen: boolean;
  characterId?: string;
  onContextModeChange: (mode: ContextMode) => void;
  onWorldEditorOpen: () => void;
  onWorldEditorClose: (replace?: boolean) => void;
  onCharacterEditorOpen: (characterId?: string) => void;
  onCharacterEditorClose: (replace?: boolean) => void;
}) {
  const [contextOpen, setContextOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [worldAnnouncement, setWorldAnnouncement] = useState("");
  const worldTabRef = useRef<HTMLButtonElement>(null);
  const worldLaunchRef = useRef<HTMLButtonElement>(null);
  const openedFromLaunchRef = useRef(false);
  const contextIsInline = useMediaQuery("(min-width: 768px)");
  const desktopIsResizable = useMediaQuery("(min-width: 1280px)");
  const { project, storyBible: bible } = workspace;
  const {
    draft,
    updateDraft,
    status,
    retry,
    flush,
    conflictKind,
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
  const sceneNavigation = useManuscriptSceneNavigation({
    manuscript: draft,
    updateDraft,
    contextIsInline,
    onCloseContext: () => setContextOpen(false),
  });
  const worldEditor = useWorldEntryEditor({
    projectId: project.id,
    open: worldEditorOpen,
    onSaved: () => {
      setWorldAnnouncement("세계관을 저장했어요.");
      onWorldEditorClose(true);
    },
    onClose: () => onWorldEditorClose(false),
  });
  const characterEditor = useCharacterCardEditor({
    projectId: project.id,
    bible,
    open: characterEditorOpen,
    mode: characterId ? "edit" : "create",
    characterId,
    onSaved: () => {
      onCharacterEditorClose(true);
    },
    onClose: () => onCharacterEditorClose(false),
  });
  useWorkspaceNavigationGuard(status, flush, worldEditor, characterEditor);
  const handleEditorOpen = () => {
    openedFromLaunchRef.current = true;
    onWorldEditorOpen();
  };
  const handleCreateCharacter = (trigger: HTMLButtonElement) => {
    worldLaunchRef.current = trigger;
    onCharacterEditorOpen();
  };
  const handleEditCharacter = (nextCharacterId: string, trigger: HTMLButtonElement) => {
    worldLaunchRef.current = trigger;
    onCharacterEditorOpen(nextCharacterId);
  };
  const handleAssistantClose = () => {
    setAssistantOpen(false);
    if (desktopIsResizable) {
      document.querySelector<HTMLElement>('[aria-label="AI 도구 열기"]')?.focus();
    }
  };
  const restoreWorldEditorFocus = (resetLaunchOrigin = true) => {
    const focusTarget = openedFromLaunchRef.current ? worldLaunchRef.current : worldTabRef.current;
    focusTarget?.focus();
    if (resetLaunchOrigin) openedFromLaunchRef.current = false;
  };
  const scene = sceneNavigation.activeScene;

  const restoreCharacterEditorFocus = () => {
    const characterTab = document.querySelector<HTMLElement>('[aria-label="인물 보기"]');
    (worldLaunchRef.current ?? characterTab)?.focus();
    worldLaunchRef.current = null;
  };

  if (!scene) {
    return (
      <main className="grid min-h-svh place-items-center bg-[#ede6dd] p-6">
        <Alert variant="destructive" className="max-w-md p-8">
          <AlertTitle>현재 집필할 장면을 찾을 수 없어요.</AlertTitle>
        </Alert>
      </main>
    );
  }

  const selection = sceneNavigation.selection;
  const selectedRange = selection && selection.start !== selection.end ? selection : null;
  const selectedText = selectedRange
    ? scene.content.slice(selectedRange.start, selectedRange.end)
    : "";
  const selectedContextTool =
    contextTools.find(({ mode }) => mode === contextMode) ?? contextTools[0];
  const assistantPanel = (
    <WritingToolPanel
      sceneContent={scene.content}
      selectedText={selectedText}
      characterNames={bible.characters.map(({ name }) => name)}
      onClose={handleAssistantClose}
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
          sceneNavigation.setSelection({
            start: updatedScene.content.length,
            end: updatedScene.content.length,
          });
        }
      }}
    />
  );

  const editor = (
    <main className="h-full min-h-0 min-w-0 overflow-y-auto p-3 sm:p-5 lg:p-6">
      <ManuscriptEditor
        ref={sceneNavigation.editorRef}
        scene={scene}
        titleEditingDisabled={status === "conflict"}
        onTitleCommit={(title) => {
          updateDraft((current) => updateSceneTitle(current, scene.id, title));
        }}
        onChange={(content) => updateDraft(updateSceneContent(draft, scene.id, content))}
        onSelectionChange={sceneNavigation.setSelection}
      />
    </main>
  );

  return (
    <div className="flex h-svh min-h-0 flex-col overflow-hidden bg-[#ede6dd]">
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
            <p className="truncate text-[11px] text-muted-foreground">
              {scene.chapterNumber}장 · {scene.title}
            </p>
          </div>
        </div>
        <AutosaveIndicator status={status} onRetry={retry} onOpenConflict={openConflictDialog} />
      </header>

      <Tabs
        value={contextMode}
        orientation="vertical"
        onValueChange={(value) => onContextModeChange(value as ContextMode)}
        className="min-h-0 flex-1 flex-row gap-0"
      >
        <nav className="flex w-14 shrink-0 flex-col items-center border-r border-border bg-sidebar py-3">
          <TabsList aria-label="집필 도메인" variant="line" className="flex-col gap-2 p-0">
            {contextTools.map((tool) => {
              const Icon = tool.icon;
              return (
                <Tooltip key={tool.mode}>
                  <TooltipTrigger asChild>
                    <TabsTrigger
                      ref={tool.mode === "world" ? worldTabRef : undefined}
                      value={tool.mode}
                      aria-label={tool.label}
                      onClick={() => {
                        if (!contextIsInline) setContextOpen(true);
                      }}
                      className="size-8 justify-center p-0 text-muted-foreground data-active:text-primary"
                    >
                      <Icon />
                    </TabsTrigger>
                  </TooltipTrigger>
                  <TooltipContent side="right">{tool.label}</TooltipContent>
                </Tooltip>
              );
            })}
          </TabsList>

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

        {!contextIsInline ? (
          <>
            <Sheet open={contextOpen} onOpenChange={setContextOpen}>
              <SheetContent side="left" className="w-full gap-0 p-0 sm:max-w-sm">
                <SheetHeader>
                  <SheetTitle asChild>
                    <span>{selectedContextTool.label}</span>
                  </SheetTitle>
                  <SheetDescription>현재 장면과 관련된 집필 정보를 확인합니다.</SheetDescription>
                </SheetHeader>
                <ScrollArea className="min-h-0 flex-1">
                  <ContextPanelContent
                    draft={draft}
                    bible={bible}
                    onAddScene={sceneNavigation.addNewScene}
                    onSelectScene={sceneNavigation.activateScene}
                    addSceneDisabled={status === "conflict"}
                    onEditWorld={handleEditorOpen}
                    editWorldButtonRef={worldLaunchRef}
                    onCreateCharacter={handleCreateCharacter}
                    onEditCharacter={handleEditCharacter}
                    characterStatus={characterEditor.announcement}
                  />
                </ScrollArea>
              </SheetContent>
            </Sheet>
            <div className="min-h-0 min-w-0 flex-1 overflow-hidden">{editor}</div>
          </>
        ) : desktopIsResizable ? (
          <ResizablePanelGroup orientation="horizontal" className="min-w-0 flex-1">
            <ResizablePanel defaultSize="20%" minSize="15%">
              <ScrollArea className="h-full bg-sidebar/90">
                <ContextPanelContent
                  draft={draft}
                  bible={bible}
                  onAddScene={sceneNavigation.addNewScene}
                  onSelectScene={sceneNavigation.activateScene}
                  addSceneDisabled={status === "conflict"}
                  onEditWorld={handleEditorOpen}
                  editWorldButtonRef={worldLaunchRef}
                  onCreateCharacter={handleCreateCharacter}
                  onEditCharacter={handleEditCharacter}
                  characterStatus={characterEditor.announcement}
                />
              </ScrollArea>
            </ResizablePanel>
            <ResizableHandle withHandle />
            <ResizablePanel defaultSize="55%" minSize="40%" className="min-h-0 overflow-hidden">
              {editor}
            </ResizablePanel>
            {assistantOpen && (
              <>
                <ResizableHandle withHandle />
                <ResizablePanel defaultSize="25%" minSize="20%" className="[&>aside]:w-full">
                  {assistantPanel}
                </ResizablePanel>
              </>
            )}
          </ResizablePanelGroup>
        ) : (
          <>
            <aside className="w-64 shrink-0 overflow-y-auto border-r border-border bg-sidebar/90">
              <ContextPanelContent
                draft={draft}
                bible={bible}
                onAddScene={sceneNavigation.addNewScene}
                onSelectScene={sceneNavigation.activateScene}
                addSceneDisabled={status === "conflict"}
                onEditWorld={handleEditorOpen}
                editWorldButtonRef={worldLaunchRef}
                onCreateCharacter={handleCreateCharacter}
                onEditCharacter={handleEditCharacter}
                characterStatus={characterEditor.announcement}
              />
            </aside>
            <div className="min-h-0 min-w-0 flex-1 overflow-hidden">{editor}</div>
          </>
        )}
        {!desktopIsResizable && (
          <Sheet open={assistantOpen} onOpenChange={setAssistantOpen}>
            <SheetContent
              side="right"
              showCloseButton={false}
              className="w-full gap-0 p-0 sm:max-w-md"
            >
              <SheetHeader className="sr-only">
                <SheetTitle asChild>
                  <span>AI 집필 도구</span>
                </SheetTitle>
                <SheetDescription>
                  현재 장면을 바탕으로 집필 제안을 만들고 원고에 적용합니다.
                </SheetDescription>
              </SheetHeader>
              {assistantPanel}
            </SheetContent>
          </Sheet>
        )}
      </Tabs>
      {worldAnnouncement && (
        <p role="status" aria-live="polite" className="sr-only">
          {worldAnnouncement}
        </p>
      )}
      <p className="sr-only" aria-live="polite">
        {sceneNavigation.announcement}
      </p>
      {worldEditor.state && (
        <>
          <WorldEditorSheet
            open={worldEditorOpen}
            state={worldEditor.state}
            onFieldChange={worldEditor.changeField}
            onAdd={worldEditor.addRow}
            onSave={() => void worldEditor.save()}
            onRequestClose={worldEditor.requestClose}
            onRetry={() => void worldEditor.retry()}
            onRequestReload={worldEditor.requestLatestReload}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              restoreWorldEditorFocus();
            }}
          />
          <WorldDiscardDialog
            intent={worldEditor.state.discardIntent}
            onCancel={worldEditor.cancelDiscard}
            onConfirm={() => void worldEditor.confirmDiscard()}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              restoreWorldEditorFocus(false);
            }}
          />
        </>
      )}
      {worldEditorOpen && !worldEditor.state && (
        <WorldEditorInitializingSheet
          open
          error={worldEditor.loadError}
          onRetry={worldEditor.retryLoad}
          onClose={() => onWorldEditorClose(false)}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            restoreWorldEditorFocus();
          }}
        />
      )}
      {characterEditorOpen && (
        <CharacterCardEditorSheet
          open
          state={characterEditor.state}
          onFieldChange={characterEditor.changeField}
          onSave={() => void characterEditor.save()}
          onRequestClose={characterEditor.requestClose}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            restoreCharacterEditorFocus();
          }}
        />
      )}
      <CharacterDiscardDialog
        state={characterEditor.state}
        onCancel={characterEditor.cancelDiscard}
        onConfirm={characterEditor.confirmDiscard}
      />
      <ManuscriptConflictDialog
        open={isConflictDialogOpen}
        kind={conflictKind ?? "scene-content"}
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

function ContextPanelContent({
  draft,
  bible,
  onAddScene,
  onSelectScene,
  addSceneDisabled,
  onEditWorld,
  editWorldButtonRef,
  onCreateCharacter,
  onEditCharacter,
  characterStatus,
}: {
  draft: ProjectWorkspaceResponse["manuscript"];
  bible: ProjectWorkspaceResponse["storyBible"];
  onAddScene: () => void;
  onSelectScene: (sceneId: string) => void;
  addSceneDisabled: boolean;
  onEditWorld: () => void;
  editWorldButtonRef: Ref<HTMLButtonElement>;
  onCreateCharacter: (trigger: HTMLButtonElement) => void;
  onEditCharacter: (characterId: string, trigger: HTMLButtonElement) => void;
  characterStatus: string;
}) {
  return (
    <>
      <TabsContent value="manuscript">
        <SceneTree
          manuscript={draft}
          onAdd={onAddScene}
          onSelect={onSelectScene}
          addDisabled={addSceneDisabled}
        />
      </TabsContent>
      <TabsContent value="characters">
        <StoryContextPanel
          bible={bible}
          mode="characters"
          onCreateCharacter={onCreateCharacter}
          onEditCharacter={onEditCharacter}
          characterStatus={characterStatus}
        />
      </TabsContent>
      <TabsContent value="world">
        <StoryContextPanel
          bible={bible}
          mode="world"
          onEditWorld={onEditWorld}
          editWorldButtonRef={editWorldButtonRef}
        />
      </TabsContent>
    </>
  );
}

function useWorkspaceNavigationGuard(
  status: ManuscriptAutosaveStatus,
  flush: () => Promise<boolean>,
  worldEditor: ReturnType<typeof useWorldEntryEditor>,
  characterEditor: ReturnType<typeof useCharacterCardEditor>,
) {
  const shouldBlock =
    status !== "saved" ||
    worldEditor.requiresDiscardConfirmation ||
    characterEditor.requiresDiscardConfirmation;
  const isHandlingBlockedNavigationRef = useRef(false);

  useBlocker({
    disabled: !shouldBlock,
    enableBeforeUnload: shouldBlock,
    shouldBlockFn: async ({ current, next }) => {
      if (
        isTabOnlyWorkspaceNavigation(current, next) &&
        !characterEditor.requiresDiscardConfirmation
      ) {
        return false;
      }

      if (isHandlingBlockedNavigationRef.current) {
        return true;
      }

      isHandlingBlockedNavigationRef.current = true;
      try {
        if (worldEditor.requiresDiscardConfirmation) {
          const confirmed = await worldEditor.confirmNavigationDiscard();
          if (!confirmed) return true;
        }
        if (characterEditor.requiresDiscardConfirmation) {
          const confirmed = await characterEditor.confirmNavigationDiscard();
          if (!confirmed) return true;
        }
        return !(await flush());
      } finally {
        isHandlingBlockedNavigationRef.current = false;
      }
    },
  });
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
