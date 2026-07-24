import { useRef } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import type { WorldDiscardIntent } from "../world-entry-editor-state";

export function WorldDiscardDialog({
  intent,
  onCancel,
  onConfirm,
  onCloseAutoFocus,
}: {
  intent?: WorldDiscardIntent;
  onCancel: () => void;
  onConfirm: () => void;
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const reload = intent === "reload-latest";
  const focusTargetRef = useRef<HTMLElement | null>(null);
  const restoreEditorFocusRef = useRef(false);
  const title = reload
    ? "현재 편집 내용을 버리고 최신 세계관을 불러올까요?"
    : "저장하지 않은 변경사항을 버릴까요?";
  return (
    <Dialog
      open={intent !== undefined}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <DialogContent
        showCloseButton={false}
        overlayClassName="z-[70]"
        className="z-[71]"
        onOpenAutoFocus={() => {
          const editor = getWorldEditor();
          const activeElement = document.activeElement;
          focusTargetRef.current =
            editor && activeElement instanceof HTMLElement && editor.contains(activeElement)
              ? activeElement
              : getWorldEditorFallback(editor);
          restoreEditorFocusRef.current = intent === "close" || intent === "reload-latest";
        }}
        onCloseAutoFocus={(event) => {
          if (!restoreEditorFocusRef.current) {
            if (intent === "close") onCloseAutoFocus?.(event);
            return;
          }

          event.preventDefault();
          const editor = getWorldEditor();
          const focusTarget = isValidWorldEditorFocusTarget(focusTargetRef.current, editor)
            ? focusTargetRef.current
            : getWorldEditorFallback(editor);
          focusTarget?.focus();
          focusTargetRef.current = null;
          restoreEditorFocusRef.current = false;
        }}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>이 작업은 되돌릴 수 없어요.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel} autoFocus>
            계속 편집
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => {
              focusTargetRef.current = null;
              restoreEditorFocusRef.current = false;
              onConfirm();
            }}
          >
            {reload ? "최신 세계관 불러오기" : "변경사항 버리기"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function getWorldEditor(): HTMLElement | null {
  return document.querySelector<HTMLElement>("[data-world-editor]");
}

function getWorldEditorFallback(editor: HTMLElement | null): HTMLElement | null {
  return (
    editor?.querySelector<HTMLElement>(
      '[data-world-field]:not(:disabled):not([aria-disabled="true"]), button:not(:disabled):not([aria-disabled="true"]), [tabindex]:not([tabindex="-1"])',
    ) ?? null
  );
}

function isValidWorldEditorFocusTarget(
  target: HTMLElement | null,
  editor: HTMLElement | null,
): target is HTMLElement {
  return Boolean(
    target &&
    editor?.contains(target) &&
    target.isConnected &&
    !target.matches(":disabled") &&
    target.getAttribute("aria-disabled") !== "true" &&
    !target.closest('[hidden], [aria-hidden="true"]'),
  );
}
