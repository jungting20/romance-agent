import { createFileRoute } from "@tanstack/react-router";

import { isTropeId } from "@/modules/story-design";
import { SetupPage } from "@/pages/new-project/setup-page";

export const Route = createFileRoute("/new_/setup")({
  validateSearch: (search: Record<string, unknown>) => ({
    trope: isTropeId(search.trope) ? search.trope : undefined,
  }),
  component: SetupPage,
});
