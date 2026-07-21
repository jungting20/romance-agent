export async function enableMocking(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITE_ENABLE_MSW === "false") {
    return;
  }

  const [
    { worker },
    { loadManuscriptSession, saveManuscriptSession },
    { hydrateMockManuscripts, setMockManuscriptPersistor },
  ] = await Promise.all([
    import("@/mocks/browser"),
    import("@/mocks/data/manuscript-session-store"),
    import("@/mocks/data/project-workspaces"),
  ]);

  try {
    const storage = window.sessionStorage;
    const session = loadManuscriptSession(storage);
    hydrateMockManuscripts(session);
    setMockManuscriptPersistor((nextSession) => saveManuscriptSession(storage, nextSession));
  } catch {
    setMockManuscriptPersistor(undefined);
    console.warn("Failed to restore the MSW manuscript session snapshot.");
  }

  await worker.start({ onUnhandledRequest: "bypass" });
}
