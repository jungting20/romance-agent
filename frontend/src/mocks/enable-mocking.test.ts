import { afterEach, describe, expect, test, vi } from "vitest";

const { start } = vi.hoisted(() => ({
  start: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/mocks/browser", () => ({
  worker: { start },
}));

import { enableMocking } from "@/mocks/enable-mocking";

describe("enableMocking", () => {
  afterEach(() => {
    start.mockClear();
    vi.unstubAllEnvs();
  });

  test("starts the browser worker in development by default", async () => {
    await enableMocking();

    expect(start).toHaveBeenCalledWith({ onUnhandledRequest: "bypass" });
  });

  test("does not start the browser worker when explicitly disabled", async () => {
    vi.stubEnv("VITE_ENABLE_MSW", "false");

    await enableMocking();

    expect(start).not.toHaveBeenCalled();
  });
});
