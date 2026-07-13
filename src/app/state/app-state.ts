import type { AppSnapshotV1 } from "@/app/infrastructure/app-storage";
import { createProjectFromTrope, type CreatedWorkspace } from "@/features/create-project";
import type { Manuscript } from "@/modules/manuscript";

export type AppAction =
  | {
      type: "workspace/created";
      workspace: CreatedWorkspace;
    }
  | {
      type: "workspace/opened";
      projectId: string;
    }
  | {
      type: "manuscript/saved";
      manuscript: Manuscript;
      updatedAt: string;
    };

export function createEmptySnapshot(): AppSnapshotV1 {
  return {
    version: 1,
    projects: [],
    concepts: [],
    storyBibles: [],
    manuscripts: [],
    lastProjectId: null,
  };
}

export function createSeedSnapshot(): AppSnapshotV1 {
  const workspace = createProjectFromTrope(
    {
      title: "은빛 정원의 약속",
      logline: "오해로 헤어진 두 사람이 오래된 온실에서 다시 만난다.",
      tropeId: "reunion",
      protagonistNames: ["서윤", "도현"],
    },
    {
      projectId: "silver-garden",
      conceptId: "silver-garden-concept",
      now: "2026-07-13T05:00:00.000Z",
    },
  );

  return appReducer(createEmptySnapshot(), {
    type: "workspace/created",
    workspace,
  });
}

export function appReducer(state: AppSnapshotV1, action: AppAction): AppSnapshotV1 {
  switch (action.type) {
    case "workspace/created":
      return {
        ...state,
        projects: [...state.projects, action.workspace.project],
        concepts: [...state.concepts, action.workspace.concept],
        storyBibles: [...state.storyBibles, action.workspace.storyBible],
        manuscripts: [...state.manuscripts, action.workspace.manuscript],
        lastProjectId: action.workspace.project.id,
      };
    case "workspace/opened":
      return {
        ...state,
        lastProjectId: action.projectId,
      };
    case "manuscript/saved":
      return {
        ...state,
        manuscripts: state.manuscripts.map((manuscript) =>
          manuscript.id === action.manuscript.id ? action.manuscript : manuscript,
        ),
        projects: state.projects.map((project) =>
          project.id === action.manuscript.projectId
            ? { ...project, updatedAt: action.updatedAt }
            : project,
        ),
      };
  }
}
