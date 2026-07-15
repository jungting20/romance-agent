import { createFileRoute } from "@tanstack/react-router";

import { WritingWorkspacePage } from "@/pages/writing-workspace/writing-workspace-page";
import {
  parseContextMode,
  type ContextMode,
} from "@/pages/writing-workspace/writing-workspace-tabs";

type WritingWorkspaceSearch = Record<string, unknown> & {
  tab?: ContextMode;
};

export const Route = createFileRoute("/projects/$projectId/write")({
  validateSearch: (search: Record<string, unknown>): WritingWorkspaceSearch => {
    if (search.tab === undefined) return search;
    return { ...search, tab: parseContextMode(search.tab) ?? "manuscript" };
  },
  component: WritingWorkspacePage,
});
