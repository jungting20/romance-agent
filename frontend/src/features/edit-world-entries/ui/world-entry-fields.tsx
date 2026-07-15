import type { ChangeEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { WorldEntryDraftErrors } from "@/modules/story-bible";

import type { WorldEditorDraftRow } from "../world-entry-editor-state";

export function WorldEntryFields({
  row,
  index,
  newIndex,
  errors,
  disabled,
  onFieldChange,
}: {
  row: WorldEditorDraftRow;
  index: number;
  newIndex: number;
  errors?: WorldEntryDraftErrors;
  disabled: boolean;
  onFieldChange: (key: string, field: "kind" | "title" | "description", value: string) => void;
}) {
  const sectionLabel = row.id ? `기존 항목 ${index + 1}` : `새 항목 ${newIndex}`;
  const idBase = `world-entry-${row.key}`;
  const change =
    (field: "kind" | "title" | "description") =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      onFieldChange(row.key, field, event.target.value);

  return (
    <Card className="overflow-visible">
      <fieldset className="space-y-4 px-4 pb-4">
        <legend className="flex items-center gap-2 px-1 text-sm font-semibold">
          {sectionLabel}
          <Badge variant="outline">{row.id ? "기존 항목" : "새 항목"}</Badge>
        </legend>
        <div className="space-y-1.5">
          <Label htmlFor={`${idBase}-kind`}>{sectionLabel} 분류</Label>
          <select
            id={`${idBase}-kind`}
            data-world-field={`${row.key}:kind`}
            value={row.kind}
            disabled={disabled}
            onChange={change("kind")}
            className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
          >
            <option value="place">장소</option>
            <option value="object">사물</option>
            <option value="rule">규칙</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idBase}-title`}>{sectionLabel} 제목</Label>
          <Input
            id={`${idBase}-title`}
            data-world-field={`${row.key}:title`}
            value={row.title}
            disabled={disabled}
            aria-invalid={errors?.title ? true : undefined}
            aria-describedby={errors?.title ? `${idBase}-title-error` : undefined}
            onChange={change("title")}
          />
          {errors?.title && (
            <p id={`${idBase}-title-error`} className="text-xs text-destructive">
              {errors.title}
            </p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${idBase}-description`}>{sectionLabel} 설명</Label>
          <Textarea
            id={`${idBase}-description`}
            data-world-field={`${row.key}:description`}
            value={row.description}
            disabled={disabled}
            aria-invalid={errors?.description ? true : undefined}
            aria-describedby={errors?.description ? `${idBase}-description-error` : undefined}
            onChange={change("description")}
          />
          {errors?.description && (
            <p id={`${idBase}-description-error`} className="text-xs text-destructive">
              {errors.description}
            </p>
          )}
        </div>
      </fieldset>
    </Card>
  );
}
