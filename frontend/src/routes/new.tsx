import { createFileRoute } from "@tanstack/react-router";

import { TropePage } from "@/pages/new-project/trope-page";

export const Route = createFileRoute("/new")({ component: TropePage });
