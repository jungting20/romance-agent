import { createFileRoute } from "@tanstack/react-router";

import { WritingWorkspacePage } from "@/pages/writing-workspace/writing-workspace-page";

export const Route = createFileRoute("/projects/$projectId/write")({
  component: WritingWorkspacePage,
});
