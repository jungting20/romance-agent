import { http, HttpResponse } from "msw";
import { describe, expect, test } from "vitest";

import { server } from "@/mocks/server";

describe("MSW test server", () => {
  test("intercepts a test-local request handler", async () => {
    server.use(
      http.get("http://localhost/__msw-probe", () => {
        return HttpResponse.json({ intercepted: true });
      }),
    );

    const response = await fetch("http://localhost/__msw-probe");

    await expect(response.json()).resolves.toEqual({ intercepted: true });
  });
});
