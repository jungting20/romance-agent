import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, test, vi } from "vitest";

import type { CompareManuscriptSceneResponse } from "@/app/infrastructure/api/contracts";
import { findMockWorkspace } from "@/mocks/data/project-workspaces";

import { ManuscriptConflictDialog } from "./manuscript-conflict-dialog";

function getComparison(): CompareManuscriptSceneResponse {
  const workspace = findMockWorkspace("silver-garden");
  if (!workspace) {
    throw new Error("Expected the seeded workspace");
  }

  return {
    sceneId: workspace.manuscript.activeSceneId,
    serverRevision: 2,
    localContent: "같은 문장\n내 문장",
    serverContent: "같은 문장\n서버 문장",
    serverManuscript: workspace.manuscript,
    rows: [
      {
        kind: "unchanged",
        localLineNumber: 1,
        localText: "같은 문장",
        serverLineNumber: 1,
        serverText: "같은 문장",
      },
      {
        kind: "local-only",
        localLineNumber: 2,
        localText: "내 문장",
        serverLineNumber: null,
        serverText: null,
      },
      {
        kind: "server-only",
        localLineNumber: null,
        localText: null,
        serverLineNumber: 2,
        serverText: "서버 문장",
      },
    ],
  };
}

describe("ManuscriptConflictDialog", () => {
  test("labels aligned local and server rows with line numbers and textual change states", () => {
    render(
      <ManuscriptConflictDialog
        open
        kind="scene-content"
        comparison={getComparison()}
        isComparing={false}
        isResolving={false}
        compareError={false}
        onOpenChange={vi.fn()}
        onKeepLocal={vi.fn()}
        onApplyServer={vi.fn()}
        onRetryCompare={vi.fn()}
      />,
    );

    expect(screen.getByRole("dialog", { name: "원고 저장 충돌 해결" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "내 편집본" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "서버 최신본" })).toBeInTheDocument();
    expect(screen.getAllByText("변경 없음")).toHaveLength(2);
    expect(screen.getByText("내 편집본에만 있음")).toBeInTheDocument();
    expect(screen.getByText("서버 최신본에만 있음")).toBeInTheDocument();
    expect(screen.getAllByText("1행")).toHaveLength(2);
    expect(screen.getAllByText("2행")).toHaveLength(2);
  });

  test("supports Escape without choosing a resolution and exposes keyboard resolution actions", async () => {
    const onOpenChange = vi.fn();
    const onKeepLocal = vi.fn();
    const onApplyServer = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <ManuscriptConflictDialog
        open
        kind="scene-content"
        comparison={getComparison()}
        isComparing={false}
        isResolving={false}
        compareError={false}
        onOpenChange={onOpenChange}
        onKeepLocal={onKeepLocal}
        onApplyServer={onApplyServer}
        onRetryCompare={vi.fn()}
      />,
    );

    expect(screen.getByText(/내 편집본을 유지하면 서버의 다른 변경은 보존/)).toBeInTheDocument();
    expect(
      screen.getByText(/서버 최신본을 적용하면 현재 로컬 편집 내용은 대체/),
    ).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onKeepLocal).not.toHaveBeenCalled();
    expect(onApplyServer).not.toHaveBeenCalled();

    rerender(
      <ManuscriptConflictDialog
        open
        kind="scene-content"
        comparison={getComparison()}
        isComparing={false}
        isResolving={false}
        compareError={false}
        onOpenChange={onOpenChange}
        onKeepLocal={onKeepLocal}
        onApplyServer={onApplyServer}
        onRetryCompare={vi.fn()}
      />,
    );
    const keepLocal = screen.getByRole("button", { name: "내 편집본 유지" });
    keepLocal.focus();
    await user.keyboard("{Enter}");
    expect(onKeepLocal).toHaveBeenCalledOnce();

    const applyServer = screen.getByRole("button", { name: "서버 최신본 적용" });
    applyServer.focus();
    await user.keyboard(" ");
    expect(onApplyServer).toHaveBeenCalledOnce();
  });

  test("keeps the dialog actionable after a comparison failure", async () => {
    const onRetryCompare = vi.fn();
    const user = userEvent.setup();
    render(
      <ManuscriptConflictDialog
        open
        kind="scene-content"
        comparison={null}
        isComparing={false}
        isResolving={false}
        compareError
        onOpenChange={vi.fn()}
        onKeepLocal={vi.fn()}
        onApplyServer={vi.fn()}
        onRetryCompare={onRetryCompare}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("편집본 비교를 불러오지 못했어요");
    await user.click(screen.getByRole("button", { name: "편집본 비교 다시 불러오기" }));
    expect(onRetryCompare).toHaveBeenCalledOnce();
  });

  test("does not allow a stale comparison to be resolved when its refresh fails", () => {
    render(
      <ManuscriptConflictDialog
        open
        kind="scene-content"
        comparison={getComparison()}
        isComparing={false}
        isResolving={false}
        compareError
        onOpenChange={vi.fn()}
        onKeepLocal={vi.fn()}
        onApplyServer={vi.fn()}
        onRetryCompare={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("최신 편집본 비교를 불러오지 못했어요");
    expect(screen.getByRole("button", { name: "내 편집본 유지" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "서버 최신본 적용" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "편집본 비교 다시 불러오기" })).toBeEnabled();
  });

  test("prevents Escape dismissal while a keep-local resolution is pending", async () => {
    const onOpenChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ManuscriptConflictDialog
        open
        kind="scene-content"
        comparison={getComparison()}
        isComparing={false}
        isResolving
        compareError={false}
        resolutionError={false}
        onOpenChange={onOpenChange}
        onKeepLocal={vi.fn()}
        onApplyServer={vi.fn()}
        onRetryCompare={vi.fn()}
        onRetryKeepLocal={vi.fn()}
      />,
    );

    await user.keyboard("{Escape}");
    expect(onOpenChange).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "원고 저장 충돌 해결" })).toBeInTheDocument();
  });

  test("focuses, traps, and returns focus through the modal lifecycle", async () => {
    const user = userEvent.setup();

    function DialogHarness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            충돌 대화상자 열기
          </button>
          <ManuscriptConflictDialog
            open={open}
            kind="scene-content"
            comparison={getComparison()}
            isComparing={false}
            isResolving={false}
            compareError={false}
            resolutionError={false}
            onOpenChange={setOpen}
            onKeepLocal={vi.fn()}
            onApplyServer={vi.fn()}
            onRetryCompare={vi.fn()}
            onRetryKeepLocal={vi.fn()}
          />
        </>
      );
    }

    render(<DialogHarness />);
    const opener = screen.getByRole("button", { name: "충돌 대화상자 열기" });
    await user.click(opener);
    const applyServer = screen.getByRole("button", { name: "서버 최신본 적용" });
    const keepLocal = screen.getByRole("button", { name: "내 편집본 유지" });

    await waitFor(() => expect(applyServer).toHaveFocus());
    await user.tab();
    expect(keepLocal).toHaveFocus();
    await user.tab();
    expect(applyServer).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(opener).toHaveFocus());
  });

  test("offers a dedicated keep-local retry after a resolution save failure", async () => {
    const onRetryKeepLocal = vi.fn();
    const user = userEvent.setup();
    render(
      <ManuscriptConflictDialog
        open
        kind="scene-content"
        comparison={getComparison()}
        isComparing={false}
        isResolving={false}
        compareError={false}
        resolutionError
        onOpenChange={vi.fn()}
        onKeepLocal={vi.fn()}
        onApplyServer={vi.fn()}
        onRetryCompare={vi.fn()}
        onRetryKeepLocal={onRetryKeepLocal}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("내 편집본을 서버에 저장하지 못했어요");
    await user.click(screen.getByRole("button", { name: "내 편집본 저장 다시 시도" }));
    expect(onRetryKeepLocal).toHaveBeenCalledOnce();
  });

  test.each([
    [
      "mouse",
      async (user: ReturnType<typeof userEvent.setup>, button: HTMLElement) => user.click(button),
    ],
    ["Enter", async (user: ReturnType<typeof userEvent.setup>) => user.keyboard("{Enter}")],
    ["Space", async (user: ReturnType<typeof userEvent.setup>) => user.keyboard(" ")],
  ])(
    "restores dialog focus to the keep-local retry after a %s resolution failure",
    async (_, activate) => {
      const user = userEvent.setup();

      function ResolutionFailureHarness() {
        const [isResolving, setIsResolving] = useState(false);
        const [resolutionError, setResolutionError] = useState(false);

        return (
          <ManuscriptConflictDialog
            open
            kind="scene-content"
            comparison={getComparison()}
            isComparing={false}
            isResolving={isResolving}
            compareError={false}
            resolutionError={resolutionError}
            onOpenChange={vi.fn()}
            onKeepLocal={() => {
              setIsResolving(true);
              window.setTimeout(() => {
                if (document.activeElement instanceof HTMLElement) {
                  document.activeElement.blur();
                }
                setIsResolving(false);
                setResolutionError(true);
              }, 0);
            }}
            onApplyServer={vi.fn()}
            onRetryCompare={vi.fn()}
            onRetryKeepLocal={vi.fn()}
          />
        );
      }

      render(<ResolutionFailureHarness />);
      const keepLocal = screen.getByRole("button", { name: "내 편집본 유지" });
      keepLocal.focus();
      await activate(user, keepLocal);

      const retry = await screen.findByRole("button", { name: "내 편집본 저장 다시 시도" });
      await waitFor(() => expect(retry).toHaveFocus());
      await user.tab();
      expect(screen.getByRole("button", { name: "서버 최신본 적용" })).toHaveFocus();
      await user.tab({ shift: true });
      expect(screen.getByRole("dialog", { name: "원고 저장 충돌 해결" })).toContainElement(
        document.activeElement as HTMLElement,
      );
    },
  );

  test("offers structural conflict actions without a scene diff table", () => {
    render(
      <ManuscriptConflictDialog
        open
        kind="scene-structure"
        comparison={null}
        isComparing={false}
        isResolving={false}
        compareError={false}
        onOpenChange={vi.fn()}
        onKeepLocal={vi.fn()}
        onApplyServer={vi.fn()}
        onRetryCompare={vi.fn()}
      />,
    );

    expect(screen.getByText("서버 최신 원고에 아직 없는 새 장면이 있어요.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "내 새 장면 유지" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "서버 최신본 적용" })).toBeEnabled();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  test("shows structural workspace loading without resolution actions", () => {
    render(
      <ManuscriptConflictDialog
        open
        kind="scene-structure"
        comparison={null}
        isComparing
        isResolving={false}
        compareError={false}
        onOpenChange={vi.fn()}
        onKeepLocal={vi.fn()}
        onApplyServer={vi.fn()}
        onRetryCompare={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("서버 최신 원고를 불러오는 중이에요.");
    expect(screen.getByRole("button", { name: "내 새 장면 유지" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "서버 최신본 적용" })).toBeDisabled();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  test("offers a structural workspace retry while confirming the local draft is preserved", async () => {
    const onRetryCompare = vi.fn();
    const user = userEvent.setup();
    render(
      <ManuscriptConflictDialog
        open
        kind="scene-structure"
        comparison={null}
        isComparing={false}
        isResolving={false}
        compareError
        onOpenChange={vi.fn()}
        onKeepLocal={vi.fn()}
        onApplyServer={vi.fn()}
        onRetryCompare={onRetryCompare}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "서버 최신 원고를 불러오지 못했어요. 현재 로컬 초안은 그대로 보관하고 있어요.",
    );
    await user.click(screen.getByRole("button", { name: "서버 최신 원고 다시 불러오기" }));
    expect(onRetryCompare).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "내 새 장면 유지" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "서버 최신본 적용" })).toBeDisabled();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
