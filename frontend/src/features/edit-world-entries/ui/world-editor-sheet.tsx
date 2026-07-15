import { useEffect, useRef } from "react";
import { LoaderCircle, Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApiRequestError } from "@/app/infrastructure/api/api-client";

import {
  isWorldEditorDirty,
  isWorldEditorFrozen,
  type WorldEditorState,
} from "../world-entry-editor-state";
import { WorldEntryFields } from "./world-entry-fields";
import { WorldEditorFeedback } from "./world-editor-feedback";

export interface WorldEditorSheetProps {
  open: boolean;
  state: WorldEditorState;
  onFieldChange: (key: string, field: "kind" | "title" | "description", value: string) => void;
  onAdd: () => void;
  onSave: () => void;
  onRequestClose: () => void;
  onRetry: () => void;
  onRequestReload: () => void;
  onCloseAutoFocus?: (event: Event) => void;
}

export function WorldEditorSheet(props: WorldEditorSheetProps) {
  const { state } = props;
  const frozen = isWorldEditorFrozen(state);
  const unavailable = state.phase.status === "unavailable";
  const titleRef = useRef<HTMLHeadingElement>(null);
  const previousRowCount = useRef(state.draft.rows.length);
  useEffect(() => {
    if (state.draft.rows.length > previousRowCount.current) {
      const added = state.draft.rows.at(-1);
      if (added && !added.id) focusWorldField(added.key, "kind");
    }
    previousRowCount.current = state.draft.rows.length;
  }, [state.draft.rows]);
  useEffect(() => {
    if (!state.firstInvalidField) return;
    focusWorldField(state.firstInvalidField.key, state.firstInvalidField.field);
  }, [state.firstInvalidField]);

  return (
    <Sheet
      open={props.open}
      onOpenChange={(open) => {
        if (!open && !frozen) props.onRequestClose();
      }}
    >
      <SheetContent
        side="right"
        showCloseButton={false}
        className="z-[60] w-full gap-0 p-0 sm:max-w-2xl"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          if (state.firstInvalidField) {
            focusWorldField(state.firstInvalidField.key, state.firstInvalidField.field);
          } else if (state.draft.rows[0]) {
            focusWorldField(state.draft.rows[0].key, "kind");
          } else {
            titleRef.current?.focus();
          }
        }}
        onEscapeKeyDown={(event) => {
          if (frozen) event.preventDefault();
        }}
        onPointerDownOutside={(event) => {
          if (frozen) event.preventDefault();
        }}
        onCloseAutoFocus={props.onCloseAutoFocus}
      >
        <SheetHeader className="border-b pr-14">
          <SheetTitle ref={titleRef} tabIndex={-1}>
            세계관 수정 및 추가
          </SheetTitle>
          <SheetDescription>
            기존 항목을 수정하거나 새 세계관 항목을 추가한 뒤 한 번에 저장합니다.
          </SheetDescription>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="세계관 편집기 닫기"
            disabled={frozen}
            onClick={props.onRequestClose}
            className="absolute right-3 top-3"
          >
            <X />
          </Button>
        </SheetHeader>
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-4 p-4">
            {frozen && (
              <p role="status" className="flex items-center gap-2 text-sm">
                <LoaderCircle className="size-4 animate-spin" />
                {state.phase.status === "saving"
                  ? "세계관을 저장하는 중이에요."
                  : "최신 세계관을 불러오는 중이에요."}
              </p>
            )}
            <WorldEditorFeedback
              state={state}
              onRetry={props.onRetry}
              onRequestReload={props.onRequestReload}
              onRequestClose={props.onRequestClose}
            />
            {state.draft.rows.length === 0 && (
              <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                아직 등록된 세계관 항목이 없어요. 새 항목을 추가해 주세요.
              </p>
            )}
            {state.draft.rows.map((row, index) => {
              const newIndex = state.draft.rows.slice(0, index + 1).filter(({ id }) => !id).length;
              return (
                <WorldEntryFields
                  key={row.key}
                  row={row}
                  index={index}
                  newIndex={newIndex}
                  errors={state.errors[row.key]}
                  disabled={frozen || unavailable}
                  onFieldChange={props.onFieldChange}
                />
              );
            })}
            <Button
              type="button"
              variant="outline"
              className="w-full"
              disabled={frozen || unavailable}
              onClick={props.onAdd}
            >
              <Plus />
              세계관 항목 추가
            </Button>
          </div>
        </ScrollArea>
        <SheetFooter className="border-t sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" disabled={frozen} onClick={props.onRequestClose}>
            취소
          </Button>
          <Button
            type="button"
            disabled={frozen || unavailable || !isWorldEditorDirty(state)}
            onClick={props.onSave}
          >
            저장
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

function focusWorldField(key: string, field: string) {
  Array.from(document.querySelectorAll<HTMLElement>("[data-world-field]"))
    .find((element) => element.dataset.worldField === `${key}:${field}`)
    ?.focus();
}

export function WorldEditorInitializingSheet({
  open,
  error,
  onRetry,
  onClose,
  onCloseAutoFocus,
}: {
  open: boolean;
  error?: ApiRequestError;
  onRetry: () => void;
  onClose: () => void;
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const unavailable =
    error?.status === 404 &&
    (error.error.code === "PROJECT_NOT_FOUND" || error.error.code === "STORY_BIBLE_NOT_FOUND");
  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <SheetContent
        side="right"
        className="z-[60] w-full sm:max-w-2xl"
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <SheetHeader>
          <SheetTitle>세계관 수정 및 추가</SheetTitle>
          <SheetDescription>세계관 편집 정보를 준비합니다.</SheetDescription>
        </SheetHeader>
        <div className="space-y-4 p-4">
          {error ? (
            <Alert variant="destructive">
              <AlertTitle>
                {unavailable
                  ? "이 세계관을 더 이상 편집할 수 없어요."
                  : "세계관을 불러오지 못했어요."}
              </AlertTitle>
              <AlertDescription>
                {unavailable ? "세계관 보기로 돌아가 주세요." : "잠시 후 다시 시도해 주세요."}
              </AlertDescription>
            </Alert>
          ) : (
            <div role="status" className="space-y-3">
              <span className="sr-only">세계관을 불러오는 중이에요.</span>
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
          )}
        </div>
        {error && (
          <SheetFooter>
            <Button type="button" variant="outline" onClick={unavailable ? onClose : onRetry}>
              {unavailable ? "세계관 보기로 돌아가기" : "다시 불러오기"}
            </Button>
          </SheetFooter>
        )}
      </SheetContent>
    </Sheet>
  );
}
