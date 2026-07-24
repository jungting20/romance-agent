import { useRef } from "react";

import type {
  CompareManuscriptSceneResponse,
  SceneDiffKind,
} from "@/app/infrastructure/api/contracts";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

interface ManuscriptConflictDialogProps {
  open: boolean;
  kind: "scene-content" | "scene-structure";
  comparison: CompareManuscriptSceneResponse | null;
  isComparing: boolean;
  isResolving: boolean;
  compareError: boolean;
  resolutionError?: boolean;
  onOpenChange: (open: boolean) => void;
  onKeepLocal: () => void;
  onApplyServer: () => void;
  onRetryCompare: () => void;
  onRetryKeepLocal?: () => void;
}

const changeLabels: Record<SceneDiffKind, string> = {
  unchanged: "변경 없음",
  "local-only": "내 편집본에만 있음",
  "server-only": "서버 최신본에만 있음",
};

export function ManuscriptConflictDialog({
  open,
  kind,
  comparison,
  isComparing,
  isResolving,
  compareError,
  resolutionError = false,
  onOpenChange,
  onKeepLocal,
  onApplyServer,
  onRetryCompare,
  onRetryKeepLocal = onKeepLocal,
}: ManuscriptConflictDialogProps) {
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const wasOpenRef = useRef(false);

  if (open && !wasOpenRef.current && typeof document !== "undefined") {
    returnFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }
  wasOpenRef.current = open;

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!isResolving) {
          onOpenChange(nextOpen);
        }
      }}
    >
      <DialogContent
        className="max-h-[calc(100svh-2rem)] max-w-5xl grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden p-0"
        showCloseButton={false}
        onEscapeKeyDown={(event) => {
          if (isResolving) {
            event.preventDefault();
          }
        }}
        onCloseAutoFocus={(event) => {
          if (returnFocusRef.current) {
            event.preventDefault();
            returnFocusRef.current.focus();
            returnFocusRef.current = null;
          }
        }}
      >
        <DialogHeader className="px-5 pt-5">
          <DialogTitle>원고 저장 충돌 해결</DialogTitle>
          <DialogDescription>
            다른 위치에서 저장된 원고와 현재 편집본을 비교한 뒤 유지할 내용을 선택해 주세요. Esc를
            눌러 닫아도 현재 편집본은 사라지지 않아요.
          </DialogDescription>
        </DialogHeader>

        <div
          className="min-h-0 overflow-y-auto overscroll-contain px-5"
          data-testid="manuscript-conflict-diff-viewport"
        >
          {kind === "scene-structure" &&
            (isComparing ? (
              <p role="status" className="grid min-h-48 place-items-center text-muted-foreground">
                서버 최신 원고를 불러오는 중이에요.
              </p>
            ) : compareError ? (
              <div className="grid min-h-48 place-items-center text-center">
                <div>
                  <p role="alert" className="text-destructive">
                    서버 최신 원고를 불러오지 못했어요. 현재 로컬 초안은 그대로 보관하고 있어요.
                  </p>
                  <Button type="button" variant="outline" className="mt-4" onClick={onRetryCompare}>
                    서버 최신 원고 다시 불러오기
                  </Button>
                </div>
              </div>
            ) : (
              <div className="grid min-h-48 place-items-center text-center">
                <div>
                  <p className="font-medium">서버 최신 원고에 아직 없는 새 장면이 있어요.</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    현재 로컬 초안은 보관하고 있습니다.
                  </p>
                </div>
              </div>
            ))}
          {kind === "scene-content" &&
            (isComparing && !comparison ? (
              <p role="status" className="grid min-h-48 place-items-center text-muted-foreground">
                편집본 차이를 불러오는 중이에요.
              </p>
            ) : compareError && !comparison ? (
              <div className="grid min-h-48 place-items-center text-center">
                <div>
                  <p role="alert" className="text-destructive">
                    편집본 비교를 불러오지 못했어요. 현재 편집본은 그대로 보관하고 있어요.
                  </p>
                  <Button type="button" variant="outline" className="mt-4" onClick={onRetryCompare}>
                    편집본 비교 다시 불러오기
                  </Button>
                </div>
              </div>
            ) : comparison ? (
              <>
                {compareError && (
                  <div
                    role="alert"
                    className="mb-3 flex items-center justify-between gap-3 rounded-lg border border-destructive/30 p-3 text-destructive"
                  >
                    <span>최신 편집본 비교를 불러오지 못했어요.</span>
                    <Button type="button" variant="outline" size="sm" onClick={onRetryCompare}>
                      편집본 비교 다시 불러오기
                    </Button>
                  </div>
                )}
                <table className="w-full table-fixed border-separate border-spacing-0 text-left">
                  <thead className="sticky top-0 z-10 bg-popover">
                    <tr>
                      <th scope="col" className="w-1/2 border-b border-r px-3 py-2 font-semibold">
                        내 편집본
                      </th>
                      <th scope="col" className="w-1/2 border-b px-3 py-2 font-semibold">
                        서버 최신본
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.rows.map((row, index) => (
                      <tr
                        key={`${row.kind}-${row.localLineNumber ?? "x"}-${row.serverLineNumber ?? "x"}-${index}`}
                      >
                        <DiffCell
                          side="local"
                          kind={row.kind}
                          lineNumber={row.localLineNumber}
                          text={row.localText}
                        />
                        <DiffCell
                          side="server"
                          kind={row.kind}
                          lineNumber={row.serverLineNumber}
                          text={row.serverText}
                        />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            ) : null)}
        </div>

        <div className="grid gap-4">
          <div className="grid gap-2 px-5 text-xs text-muted-foreground sm:grid-cols-2">
            <p>
              내 편집본을 유지하면 서버의 다른 변경은 보존하고 이 장면만 현재 내용으로 저장해요.
            </p>
            <p>
              서버 최신본을 적용하면 현재 로컬 편집 내용은 대체되고 서버의 전체 원고를 사용해요.
            </p>
          </div>

          {resolutionError && (
            <p role="alert" className="px-5 text-sm text-destructive">
              내 편집본을 서버에 저장하지 못했어요. 현재 편집본을 보관하고 있으니 다시 시도해
              주세요.
            </p>
          )}

          <DialogFooter className="mx-0 mb-0 px-5">
            <Button
              type="button"
              variant="outline"
              disabled={
                isComparing ||
                isResolving ||
                compareError ||
                (kind === "scene-content" && !comparison)
              }
              onClick={onApplyServer}
              autoFocus
            >
              서버 최신본 적용
            </Button>
            <Button
              type="button"
              disabled={
                isComparing ||
                isResolving ||
                compareError ||
                (kind === "scene-content" && !comparison)
              }
              onClick={resolutionError ? onRetryKeepLocal : onKeepLocal}
            >
              {resolutionError
                ? "내 편집본 저장 다시 시도"
                : kind === "scene-structure"
                  ? "내 새 장면 유지"
                  : "내 편집본 유지"}
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DiffCell({
  side,
  kind,
  lineNumber,
  text,
}: {
  side: "local" | "server";
  kind: SceneDiffKind;
  lineNumber: number | null;
  text: string | null;
}) {
  const visible = text !== null;
  const label = visible ? changeLabels[kind] : null;

  return (
    <td
      className={cn(
        "h-full align-top border-b px-3 py-2",
        side === "local" && "border-r",
        visible && kind === "local-only" && "bg-amber-50",
        visible && kind === "server-only" && "bg-emerald-50",
      )}
    >
      {visible ? (
        <div className="grid grid-cols-[auto_1fr] gap-x-2">
          <span className="text-xs tabular-nums text-muted-foreground">{lineNumber}행</span>
          <div className="min-w-0">
            <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
            <p className="mt-0.5 whitespace-pre-wrap break-words">{text || " "}</p>
          </div>
        </div>
      ) : (
        <span aria-hidden="true">&nbsp;</span>
      )}
    </td>
  );
}
