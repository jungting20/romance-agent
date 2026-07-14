import { http, HttpResponse, type RequestHandler } from "msw";

import { healthResponse } from "@/mocks/data/health";

export const healthHandlers: RequestHandler[] = [
  http.get("/health", () => HttpResponse.json(healthResponse)),
];
