import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useReducer,
} from "react";

import { createAppStorage, type StoragePort } from "@/app/infrastructure/app-storage";
import {
  createProjectFromTrope,
  type CreateProjectFromTropeInput,
} from "@/features/create-project";
import type { Manuscript } from "@/modules/manuscript";

import { appReducer, createSeedSnapshot } from "./app-state";

export interface AppContextValue {
  state: ReturnType<typeof createSeedSnapshot>;
  createProject: (input: CreateProjectFromTropeInput) => string;
  openProject: (projectId: string) => void;
  saveManuscript: (manuscript: Manuscript) => void;
}

export interface AppProviderProps extends PropsWithChildren {
  storage?: StoragePort;
  createId?: () => string;
  now?: () => string;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({
  children,
  storage = window.localStorage,
  createId = () => crypto.randomUUID(),
  now = () => new Date().toISOString(),
}: AppProviderProps) {
  const repository = useMemo(() => createAppStorage(storage), [storage]);
  const [state, dispatch] = useReducer(
    appReducer,
    undefined,
    () => repository.load() ?? createSeedSnapshot(),
  );

  useEffect(() => {
    repository.save(state);
  }, [repository, state]);

  const value = useMemo<AppContextValue>(
    () => ({
      state,
      createProject(input) {
        const projectId = createId();
        const workspace = createProjectFromTrope(input, {
          projectId,
          conceptId: `${projectId}-concept`,
          now: now(),
        });
        dispatch({ type: "workspace/created", workspace });
        return projectId;
      },
      openProject(projectId) {
        dispatch({ type: "workspace/opened", projectId });
      },
      saveManuscript(manuscript) {
        dispatch({
          type: "manuscript/saved",
          manuscript,
          updatedAt: now(),
        });
      },
    }),
    [createId, now, state],
  );

  return <AppContext value={value}>{children}</AppContext>;
}

export function useApp(): AppContextValue {
  const context = useContext(AppContext);

  if (!context) {
    throw new Error("useApp must be used within AppProvider");
  }

  return context;
}
