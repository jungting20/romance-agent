import type { RequestHandler } from "msw";

import { healthHandlers } from "@/mocks/handlers/health";
import { projectHandlers } from "@/mocks/handlers/projects";

export const handlers: RequestHandler[] = [...healthHandlers, ...projectHandlers];
