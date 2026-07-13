export type ProjectId = string;

export interface Project {
  id: ProjectId;
  title: string;
  logline: string;
  tropeId: string;
  updatedAt: string;
}

export interface CreateProjectInput extends Project {}

export function createProject(input: CreateProjectInput): Project {
  const title = input.title.trim();

  if (!title) {
    throw new Error("작품 제목을 입력해 주세요.");
  }

  return {
    ...input,
    title,
    logline: input.logline.trim(),
  };
}

export function sortProjectsByRecent(projects: Project[]): Project[] {
  return [...projects].sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
}
