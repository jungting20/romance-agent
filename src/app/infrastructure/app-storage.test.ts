import { describe, expect, test } from "vitest";

describe("localStorage app repository", () => {
  test("round-trips a versioned application snapshot", async () => {
    const { createAppStorage } = await import("./app-storage");
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };
    const repository = createAppStorage(storage);
    const snapshot = {
      version: 1 as const,
      projects: [],
      concepts: [],
      storyBibles: [],
      manuscripts: [],
      lastProjectId: null,
    };

    repository.save(snapshot);

    expect(repository.load()).toEqual(snapshot);
  });

  test("returns null for corrupt or unsupported data", async () => {
    const { createAppStorage } = await import("./app-storage");
    const storage = {
      getItem: () => '{"version":99}',
      setItem: () => undefined,
    };

    expect(createAppStorage(storage).load()).toBeNull();
  });
});
