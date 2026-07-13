import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { describe, expect, test } from "vitest";

describe("AppProvider", () => {
  test("loads saved state and persists newly created workspaces", async () => {
    const { AppProvider, useApp } = await import("./app-provider");
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };
    const wrapper = ({ children }: PropsWithChildren) => (
      <AppProvider
        storage={storage}
        createId={() => "new-project"}
        now={() => "2026-07-13T09:00:00.000Z"}
      >
        {children}
      </AppProvider>
    );
    const { result } = renderHook(() => useApp(), { wrapper });

    act(() => {
      result.current.createProject({
        title: "계약의 온도",
        logline: "계약 연애가 진심이 된다.",
        tropeId: "contract-romance",
        protagonistNames: ["하린", "정우"],
      });
    });

    expect(result.current.state.projects).toHaveLength(2);
    await waitFor(() => expect(values.get("romance-agent:v1")).toBeTruthy());
  });
});
