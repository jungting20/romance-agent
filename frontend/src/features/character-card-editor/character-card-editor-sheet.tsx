import { forwardRef, useEffect, useRef } from "react";
import { LoaderCircle, X } from "lucide-react";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import type { CharacterDraftValue } from "@/modules/story-bible";

import type { CharacterCardEditorState } from "./use-character-card-editor";

export function CharacterCardEditorSheet({
  open,
  state,
  onFieldChange,
  onSave,
  onRequestClose,
  onCloseAutoFocus,
}: {
  open: boolean;
  state: CharacterCardEditorState;
  onFieldChange: (field: keyof CharacterDraftValue, value: string) => void;
  onSave: () => void;
  onRequestClose: () => void;
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const nameRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (state.errors.name) nameRef.current?.focus();
  }, [state.errors.name]);
  const title =
    state.mode === "create" ? "새 인물 등록" : `${state.character?.name ?? "인물"} 수정`;
  return (
    <Sheet open={open} onOpenChange={(next) => !next && !state.isSaving && onRequestClose()}>
      <SheetContent
        side="right"
        showCloseButton={false}
        className="z-[60] w-full gap-0 p-0 sm:max-w-2xl"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          nameRef.current?.focus();
        }}
        onEscapeKeyDown={(event) => state.isSaving && event.preventDefault()}
        onPointerDownOutside={(event) => state.isSaving && event.preventDefault()}
        onCloseAutoFocus={onCloseAutoFocus}
      >
        <SheetHeader className="border-b pr-14">
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>
            {state.mode === "create"
              ? "인물 기준 정보를 입력하면 서버에서 인물 ID를 생성합니다."
              : "이 인물의 Story Bible 기준 정보를 수정합니다."}
          </SheetDescription>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="인물 편집기 닫기"
            disabled={state.isSaving}
            onClick={onRequestClose}
            className="absolute right-3 top-3"
          >
            <X />
          </Button>
        </SheetHeader>
        <ScrollArea className="min-h-0 flex-1">
          <form
            id="character-card-form"
            noValidate
            className="space-y-5 p-4"
            onSubmit={(event) => {
              event.preventDefault();
              onSave();
            }}
          >
            {state.isSaving && (
              <p role="status" className="flex items-center gap-2 text-sm">
                <LoaderCircle className="size-4 animate-spin" /> 인물을 저장하는 중이에요.
              </p>
            )}
            {state.unavailable && (
              <Alert variant="destructive">
                <AlertTitle>
                  {state.saveError
                    ? "이 인물을 더 이상 편집할 수 없어요."
                    : "이 인물을 찾을 수 없어요."}
                </AlertTitle>
                <AlertDescription>
                  등장인물 목록으로 돌아가 다른 인물을 선택해 주세요.
                </AlertDescription>
                <AlertAction>
                  <Button type="button" variant="outline" onClick={onRequestClose}>
                    등장인물 목록으로 돌아가기
                  </Button>
                </AlertAction>
              </Alert>
            )}
            {state.errors.name && (
              <Alert variant="destructive">
                <AlertTitle>인물 정보를 확인해 주세요.</AlertTitle>
                <AlertDescription>{state.errors.name}</AlertDescription>
              </Alert>
            )}
            {state.saveError && !state.unavailable && (
              <Alert variant="destructive">
                <AlertTitle>인물을 저장하지 못했어요.</AlertTitle>
                <AlertDescription>
                  {state.saveError.error.message} 입력한 내용은 그대로 유지했어요.
                </AlertDescription>
              </Alert>
            )}
            {state.mode === "edit" && state.character && (
              <div className="space-y-2">
                <Label htmlFor="character-id">인물 ID</Label>
                <Input id="character-id" value={state.character.id} readOnly />
              </div>
            )}
            <fieldset disabled={state.isSaving || state.unavailable} className="space-y-4">
              <CharacterInput
                ref={nameRef}
                field="name"
                label="이름"
                value={state.draft.name}
                required
                error={state.errors.name}
                onChange={onFieldChange}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <CharacterInput
                  field="gender"
                  label="성별"
                  value={state.draft.gender}
                  onChange={onFieldChange}
                />
                <CharacterInput
                  field="age"
                  label="나이"
                  value={state.draft.age}
                  onChange={onFieldChange}
                />
              </div>
              <CharacterInput
                field="role"
                label="역할"
                value={state.draft.role}
                onChange={onFieldChange}
              />
              <CharacterTextarea
                field="personality"
                label="성격"
                value={state.draft.personality}
                onChange={onFieldChange}
              />
              <CharacterTextarea
                field="proseStyle"
                label="문체"
                value={state.draft.proseStyle}
                onChange={onFieldChange}
              />
              <CharacterTextarea
                field="dialogueStyle"
                label="대사 스타일"
                value={state.draft.dialogueStyle}
                onChange={onFieldChange}
              />
              <CharacterTextarea
                field="desire"
                label="기본 욕망"
                value={state.draft.desire}
                onChange={onFieldChange}
              />
              <CharacterTextarea
                field="hiddenFeeling"
                label="숨은 감정"
                value={state.draft.hiddenFeeling}
                onChange={onFieldChange}
              />
            </fieldset>
          </form>
        </ScrollArea>
        <SheetFooter className="border-t sm:flex-row sm:justify-end">
          <Button
            type="button"
            variant="outline"
            disabled={state.isSaving}
            onClick={onRequestClose}
          >
            취소
          </Button>
          <Button
            type="submit"
            form="character-card-form"
            disabled={state.isSaving || state.unavailable || !state.canSave}
          >
            {state.isSaving ? "저장 중…" : state.saveError ? "다시 저장" : "저장"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

const CharacterInput = forwardRef<HTMLInputElement, FieldProps & { required?: boolean }>(
  ({ field, label, value, error, required, onChange }, ref) => {
    const id = `character-${field}`;
    return (
      <div className="space-y-2">
        <Label htmlFor={id}>
          {label}
          {required ? " *" : ""}
        </Label>
        <Input
          ref={ref}
          id={id}
          type="text"
          value={value}
          required={required}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => onChange(field, event.target.value)}
        />
        {error && (
          <p id={`${id}-error`} className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
    );
  },
);
CharacterInput.displayName = "CharacterInput";

function CharacterTextarea({ field, label, value, onChange }: FieldProps) {
  const id = `character-${field}`;
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Textarea id={id} value={value} onChange={(event) => onChange(field, event.target.value)} />
    </div>
  );
}

interface FieldProps {
  field: keyof CharacterDraftValue;
  label: string;
  value: string;
  error?: string;
  onChange: (field: keyof CharacterDraftValue, value: string) => void;
}

export function CharacterDiscardDialog({
  state,
  onCancel,
  onConfirm,
}: {
  state: CharacterCardEditorState;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={state.discardIntent !== undefined} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent showCloseButton={false} overlayClassName="z-[70]" className="z-[71]">
        <DialogHeader>
          <DialogTitle>저장하지 않은 변경사항을 버릴까요?</DialogTitle>
          <DialogDescription>이 작업은 되돌릴 수 없어요.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel} autoFocus>
            계속 편집
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm}>
            변경사항 버리기
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
