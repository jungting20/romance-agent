import { deepEqual } from "@tanstack/react-router";

export const contextModes = ["manuscript", "characters", "world"] as const;

export type ContextMode = (typeof contextModes)[number];

export function parseContextMode(value: unknown): ContextMode | undefined {
  return contextModes.find((mode) => mode === value);
}

interface WorkspaceNavigationLocation {
  pathname: string;
  search: Record<string, unknown>;
}

export function isTabOnlyWorkspaceNavigation(
  current: WorkspaceNavigationLocation,
  next: WorkspaceNavigationLocation,
): boolean {
  if (current.pathname !== next.pathname) return false;

  const { tab: _currentTab, ...currentSearch } = current.search;
  const { tab: _nextTab, ...nextSearch } = next.search;
  return deepEqual(currentSearch, nextSearch);
}
