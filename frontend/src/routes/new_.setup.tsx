import { createFileRoute } from "@tanstack/react-router";

import { SetupPage } from "@/pages/new-project/setup-page";

export const Route = createFileRoute("/new_/setup")({
  validateSearch: (search: Record<string, unknown>) => ({
    trope: typeof search.trope === "string" ? search.trope : undefined,
  }),
  component: SetupPage,
});
