import {
  createBrowserRouter,
  createMemoryRouter,
  Navigate,
  Outlet,
  type RouteObject,
} from "react-router-dom";

import { TooltipProvider } from "@/components/ui/tooltip";
import { LibraryPage } from "@/pages/library/library-page";
import { SetupPage } from "@/pages/new-project/setup-page";
import { TropePage } from "@/pages/new-project/trope-page";
import { WritingWorkspacePage } from "@/pages/writing-workspace/writing-workspace-page";

const appRoutes: RouteObject[] = [
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <LibraryPage /> },
      { path: "new", element: <TropePage /> },
      { path: "new/setup", element: <SetupPage /> },
      { path: "projects/:projectId/write", element: <WritingWorkspacePage /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
];

function AppLayout() {
  return (
    <TooltipProvider>
      <Outlet />
    </TooltipProvider>
  );
}

export function createAppBrowserRouter() {
  return createBrowserRouter(appRoutes);
}

export function createAppMemoryRouter(initialEntries: string[]) {
  return createMemoryRouter(appRoutes, { initialEntries });
}
