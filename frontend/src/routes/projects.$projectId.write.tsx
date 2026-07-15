import { createFileRoute } from "@tanstack/react-router";

import { WritingWorkspacePage } from "@/pages/writing-workspace/writing-workspace-page";
import {
  parseContextMode,
  parseWorkspacePanel,
  type ContextMode,
  type WorkspacePanel,
} from "@/pages/writing-workspace/writing-workspace-tabs";

type ValidatedWritingWorkspaceSearch = Record<string, unknown> & {
  tab?: ContextMode;
  panel?: WorkspacePanel | null;
};

export const Route = createFileRoute("/projects/$projectId/write")({
  validateSearch: (search: Record<string, unknown>): ValidatedWritingWorkspaceSearch => {
    const validated: ValidatedWritingWorkspaceSearch = { ...search };
    if (search.tab !== undefined) validated.tab = parseContextMode(search.tab) ?? "manuscript";
    if (search.panel !== undefined) validated.panel = parseWorkspacePanel(search.panel) ?? null;
    return validated;
  },
  component: WritingWorkspacePage,
});
