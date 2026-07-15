import { createFileRoute } from "@tanstack/react-router";

import { LibraryPage } from "@/pages/library/library-page";

export const Route = createFileRoute("/")({ component: LibraryPage });
