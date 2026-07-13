import { createInitialManuscript, type Manuscript } from "@/modules/manuscript";
import { createProject, type Project } from "@/modules/projects";
import { createInitialStoryBible, type StoryBible } from "@/modules/story-bible";
import { createStoryConcept, type StoryConcept } from "@/modules/story-design";

export interface CreateProjectFromTropeInput {
  title: string;
  logline: string;
  tropeId: string;
  protagonistNames: [string, string];
}

export interface CreateProjectDependencies {
  projectId: string;
  conceptId: string;
  now: string;
}

export interface CreatedWorkspace {
  project: Project;
  concept: StoryConcept;
  storyBible: StoryBible;
  manuscript: Manuscript;
}

export function createProjectFromTrope(
  input: CreateProjectFromTropeInput,
  dependencies: CreateProjectDependencies,
): CreatedWorkspace {
  const project = createProject({
    id: dependencies.projectId,
    title: input.title,
    logline: input.logline,
    tropeId: input.tropeId,
    updatedAt: dependencies.now,
  });
  const concept = createStoryConcept({
    id: dependencies.conceptId,
    projectId: project.id,
    tropeId: input.tropeId,
    logline: input.logline,
    protagonistNames: input.protagonistNames,
  });

  return {
    project,
    concept,
    storyBible: createInitialStoryBible(project.id, concept.protagonistNames),
    manuscript: createInitialManuscript(project.id),
  };
}
