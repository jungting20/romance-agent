export async function enableMocking(): Promise<void> {
  if (!import.meta.env.DEV) {
    return;
  }

  const { worker } = await import("@/mocks/browser");

  await worker.start({ onUnhandledRequest: "bypass" });
}
