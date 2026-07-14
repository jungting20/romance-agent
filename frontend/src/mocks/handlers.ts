import type { RequestHandler } from "msw";

import { projectHandlers } from "@/mocks/handlers/projects";

export const handlers: RequestHandler[] = [...projectHandlers];
