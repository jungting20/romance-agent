import { deepEqual } from "@tanstack/react-router";

export const contextModes = ["manuscript", "characters", "world"] as const;

export type ContextMode = (typeof contextModes)[number];
export type WorkspacePanel = "world-editor";

export interface WritingWorkspaceSearch extends Record<string, unknown> {
  tab?: ContextMode;
  panel?: WorkspacePanel;
}

export function parseContextMode(value: unknown): ContextMode | undefined {
  return contextModes.find((mode) => mode === value);
}

export function parseWorkspacePanel(value: unknown): WorkspacePanel | undefined {
  return value === "world-editor" ? value : undefined;
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
