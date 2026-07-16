export async function enableMocking(): Promise<void> {
  if (!import.meta.env.DEV || import.meta.env.VITE_ENABLE_MSW === "false") {
    return;
  }

  const { worker } = await import("@/mocks/browser");

  await worker.start({ onUnhandledRequest: "bypass" });
}
