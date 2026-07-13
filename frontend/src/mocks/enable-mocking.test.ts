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
  });

  test("starts the browser worker in development", async () => {
    await enableMocking();

    expect(start).toHaveBeenCalledWith({ onUnhandledRequest: "bypass" });
  });
});
