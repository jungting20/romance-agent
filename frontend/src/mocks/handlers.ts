import type { RequestHandler } from "msw";

import { healthHandlers } from "@/mocks/handlers/health";
import { projectHandlers } from "@/mocks/handlers/projects";
import { storyBibleHandlers } from "@/mocks/handlers/story-bible";

export const handlers: RequestHandler[] = [
  ...healthHandlers,
  ...projectHandlers,
  ...storyBibleHandlers,
];
