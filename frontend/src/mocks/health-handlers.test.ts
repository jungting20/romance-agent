import { describe, expect, test } from "vitest";

describe("health API handler", () => {
  test("returns the contracted process health response", async () => {
    const response = await fetch(`${window.location.origin}/health`);
    const body: unknown = await response.json();

    expect(response.status).toBe(200);
    expect(body).toEqual({ status: "ok" });
  });
});
