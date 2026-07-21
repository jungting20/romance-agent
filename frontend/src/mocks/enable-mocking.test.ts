import { afterEach, describe, expect, test, vi } from "vitest";

const {
  hydrateMockManuscripts,
  loadManuscriptSession,
  saveManuscriptSession,
  setMockManuscriptPersistor,
  start,
} = vi.hoisted(() => ({
  hydrateMockManuscripts: vi.fn(),
  loadManuscriptSession: vi.fn(),
  saveManuscriptSession: vi.fn(),
  setMockManuscriptPersistor: vi.fn(),
  start: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/mocks/browser", () => ({
  worker: { start },
}));

vi.mock("@/mocks/data/manuscript-session-store", () => ({
  loadManuscriptSession,
  saveManuscriptSession,
}));

vi.mock("@/mocks/data/project-workspaces", () => ({
  hydrateMockManuscripts,
  setMockManuscriptPersistor,
}));

import { enableMocking } from "@/mocks/enable-mocking";

describe("enableMocking", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  test("hydrates and connects the session before starting the development worker", async () => {
    const session = { schemaVersion: 1 as const, entries: [] };
    loadManuscriptSession.mockReturnValue(session);

    await enableMocking();

    expect(loadManuscriptSession).toHaveBeenCalledWith(window.sessionStorage);
    expect(hydrateMockManuscripts).toHaveBeenCalledWith(session);
    expect(setMockManuscriptPersistor).toHaveBeenCalledWith(expect.any(Function));
    expect(loadManuscriptSession.mock.invocationCallOrder[0]).toBeLessThan(
      hydrateMockManuscripts.mock.invocationCallOrder[0],
    );
    expect(hydrateMockManuscripts.mock.invocationCallOrder[0]).toBeLessThan(
      setMockManuscriptPersistor.mock.invocationCallOrder[0],
    );
    expect(setMockManuscriptPersistor.mock.invocationCallOrder[0]).toBeLessThan(
      start.mock.invocationCallOrder[0],
    );
    expect(start).toHaveBeenCalledWith({ onUnhandledRequest: "bypass" });

    const persist = setMockManuscriptPersistor.mock.calls[0][0];
    persist(session);
    expect(saveManuscriptSession).toHaveBeenCalledWith(window.sessionStorage, session);
  });

  test("does not start the browser worker when explicitly disabled", async () => {
    vi.stubEnv("VITE_ENABLE_MSW", "false");

    await enableMocking();

    expect(start).not.toHaveBeenCalled();
    expect(loadManuscriptSession).not.toHaveBeenCalled();
    expect(saveManuscriptSession).not.toHaveBeenCalled();
  });

  test("does not access manuscript storage in production", async () => {
    vi.stubEnv("DEV", false);

    await enableMocking();

    expect(start).not.toHaveBeenCalled();
    expect(loadManuscriptSession).not.toHaveBeenCalled();
    expect(saveManuscriptSession).not.toHaveBeenCalled();
  });

  test("starts with seed memory when browser storage access fails", async () => {
    const warning = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    loadManuscriptSession.mockImplementation(() => {
      throw new DOMException("Access denied", "SecurityError");
    });

    await enableMocking();

    expect(hydrateMockManuscripts).not.toHaveBeenCalled();
    expect(setMockManuscriptPersistor).toHaveBeenCalledWith(undefined);
    expect(start).toHaveBeenCalledWith({ onUnhandledRequest: "bypass" });
    expect(warning).toHaveBeenCalledWith("Failed to restore the MSW manuscript session snapshot.");
    warning.mockRestore();
  });
});
