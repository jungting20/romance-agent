import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
});
