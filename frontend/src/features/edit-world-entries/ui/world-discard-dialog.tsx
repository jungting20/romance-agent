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
}: {
  intent?: WorldDiscardIntent;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const reload = intent === "reload-latest";
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
      <DialogContent showCloseButton={false} className="z-[70]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>이 작업은 되돌릴 수 없어요.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel} autoFocus>
            계속 편집
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm}>
            {reload ? "최신 세계관 불러오기" : "변경사항 버리기"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
