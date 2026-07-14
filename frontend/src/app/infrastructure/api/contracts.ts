export type TropeId = "rivals-to-lovers" | "contract-romance" | "reunion" | "friends-to-lovers";

export type ApiErrorCode =
  | "MALFORMED_REQUEST"
  | "PROJECT_NOT_FOUND"
  | "MANUSCRIPT_NOT_FOUND"
  | "SCENE_NOT_FOUND"
  | "INVALID_SCENE_REFERENCE"
  | "MANUSCRIPT_REVISION_CONFLICT"
  | "INVALID_TITLE"
  | "INVALID_TROPE"
  | "INVALID_PROTAGONISTS"
  | "INVALID_MANUSCRIPT"
  | "INTERNAL_ERROR";

export interface ApiProject {
  id: string;
  title: string;
  logline: string;
  tropeId: TropeId;
  updatedAt: string;
}

export interface ApiStoryConcept {
  id: string;
  projectId: string;
  tropeId: TropeId;
  logline: string;
  protagonistNames: [string, string];
}

export interface ApiCharacter {
  id: string;
  name: string;
  role: "protagonist";
  desire: string;
  hiddenFeeling: string;
}

export interface ApiWorldEntry {
  id: string;
  kind: "place" | "object" | "rule";
  title: string;
  description: string;
}

export interface ApiStoryBible {
  projectId: string;
  characters: ApiCharacter[];
  worldEntries: ApiWorldEntry[];
}

export interface ApiScene {
  id: string;
  title: string;
  chapterNumber: number;
  content: string;
  relatedCharacterIds: string[];
  relatedWorldEntryIds: string[];
}

export interface ApiManuscript {
  id: string;
  projectId: string;
  scenes: ApiScene[];
  activeSceneId: string;
}

export interface ProjectWorkspaceResponse {
  project: ApiProject;
  concept: ApiStoryConcept;
  storyBible: ApiStoryBible;
  manuscript: ApiManuscript;
  manuscriptRevision: number;
}

export interface ProjectListResponse {
  items: ApiProject[];
}

export interface CreateProjectRequest {
  title: string;
  logline: string;
  tropeId: TropeId;
  protagonistNames: [string, string];
}

export interface SaveManuscriptRequest {
  manuscript: ApiManuscript;
  expectedRevision: number;
}

export interface SaveManuscriptResponse {
  manuscript: ApiManuscript;
  manuscriptRevision: number;
  projectActivity: { projectId: string; updatedAt: string };
}

export type SceneDiffKind = "unchanged" | "local-only" | "server-only";

export interface SceneDiffRow {
  kind: SceneDiffKind;
  localLineNumber: number | null;
  localText: string | null;
  serverLineNumber: number | null;
  serverText: string | null;
}

export interface CompareManuscriptSceneRequest {
  sceneId: string;
  localContent: string;
}

export interface CompareManuscriptSceneResponse {
  sceneId: string;
  serverRevision: number;
  localContent: string;
  serverContent: string;
  serverManuscript: ApiManuscript;
  rows: SceneDiffRow[];
}

export interface FieldError {
  path: string;
  message: string;
}

export interface ApiError {
  code: ApiErrorCode;
  message: string;
  fieldErrors: FieldError[];
}
