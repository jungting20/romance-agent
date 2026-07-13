import { Navigate, Route, Routes } from "react-router-dom";

import { TooltipProvider } from "@/components/ui/tooltip";
import { LibraryPage } from "@/pages/library/library-page";
import { SetupPage } from "@/pages/new-project/setup-page";
import { TropePage } from "@/pages/new-project/trope-page";
import { WritingWorkspacePage } from "@/pages/writing-workspace/writing-workspace-page";

export function AppRoutes() {
  return (
    <TooltipProvider>
      <Routes>
        <Route path="/" element={<LibraryPage />} />
        <Route path="/new" element={<TropePage />} />
        <Route path="/new/setup" element={<SetupPage />} />
        <Route path="/projects/:projectId/write" element={<WritingWorkspacePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </TooltipProvider>
  );
}
