import { createMemoryHistory, createRouter, type RouterHistory } from "@tanstack/react-router";

import { routeTree } from "@/routeTree.gen";

export function createAppRouter(options: { history?: RouterHistory } = {}) {
  return createRouter({
    routeTree,
    history: options.history,
    defaultPreload: "intent",
  });
}

export function createAppMemoryRouter(initialEntries: string[]) {
  return createAppRouter({ history: createMemoryHistory({ initialEntries }) });
}

export const router = createAppRouter();

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
