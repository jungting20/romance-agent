export const projectKeys = {
  all: ["projects"] as const,
  list: () => [...projectKeys.all, "list"] as const,
  workspace: (projectId: string) => [...projectKeys.all, "workspace", projectId] as const,
};
