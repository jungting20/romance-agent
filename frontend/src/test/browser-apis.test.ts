import { describe, expect, test } from "vitest";

describe("browser API test environment", () => {
  test("provides ResizeObserver for components that measure their content", () => {
    expect(globalThis.ResizeObserver).toBeDefined();
  });
});
