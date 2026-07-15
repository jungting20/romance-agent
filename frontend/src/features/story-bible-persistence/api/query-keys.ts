export const storyBibleKeys = {
  all: ["story-bible"] as const,
  project: (projectId: string) => ["story-bible", projectId] as const,
};
