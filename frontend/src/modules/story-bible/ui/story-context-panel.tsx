import type { Ref } from "react";
import { Heart, MapPin } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { StoryBible } from "@/modules/story-bible";

interface StoryContextPanelProps {
  bible: StoryBible;
  mode: "characters" | "world";
  onEditWorld?: () => void;
  editWorldButtonRef?: Ref<HTMLButtonElement>;
  onCreateCharacter?: (trigger: HTMLButtonElement) => void;
  onEditCharacter?: (characterId: string, trigger: HTMLButtonElement) => void;
  characterStatus?: string;
}

const worldKindLabels = {
  place: "장소",
  object: "사물",
  rule: "규칙",
} as const;

export function StoryContextPanel({
  bible,
  mode,
  onEditWorld,
  editWorldButtonRef,
  onCreateCharacter,
  onEditCharacter,
  characterStatus,
}: StoryContextPanelProps) {
  if (mode === "world") {
    return (
      <div className="h-full p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">세계관</h2>
          <Button
            ref={editWorldButtonRef}
            type="button"
            size="sm"
            variant="outline"
            onClick={onEditWorld}
          >
            세계관 수정 및 추가
          </Button>
        </div>
        <div className="space-y-3">
          {bible.worldEntries.length === 0 && (
            <p className="text-xs text-muted-foreground">아직 등록된 세계관 항목이 없어요.</p>
          )}
          {bible.worldEntries.map((entry) => (
            <Card key={entry.id} className="gap-2 border-sidebar-border bg-card py-3 shadow-none">
              <CardContent className="px-3">
                <div className="mb-2 flex items-center gap-2">
                  <MapPin className="size-4 text-primary" />
                  <Badge variant="outline" className="text-[9px]">
                    {worldKindLabels[entry.kind]}
                  </Badge>
                  <p className="text-xs font-semibold">{entry.title}</p>
                </div>
                <p className="text-[11px] leading-5 text-muted-foreground">{entry.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full p-4">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">등장인물</h2>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={(event) => onCreateCharacter?.(event.currentTarget)}
        >
          새 인물 등록
        </Button>
      </div>
      {characterStatus && (
        <p
          role="status"
          aria-live="polite"
          className="mb-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-xs text-foreground"
        >
          {characterStatus}
        </p>
      )}
      <div className="space-y-3">
        {bible.characters.length === 0 && (
          <p className="text-xs text-muted-foreground">아직 등록된 인물이 없어요.</p>
        )}
        {bible.characters.map((character) => (
          <Card key={character.id} className="gap-2 border-sidebar-border bg-card py-3 shadow-none">
            <CardContent className="px-3">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="grid size-7 place-items-center rounded-full bg-secondary text-xs font-semibold text-primary">
                    {character.name.slice(0, 1)}
                  </span>
                  <p className="text-xs font-semibold">{character.name}</p>
                </div>
                {character.role && (
                  <Badge variant="outline" className="text-[9px]">
                    {character.role}
                  </Badge>
                )}
              </div>
              <p className="flex gap-1.5 text-[11px] leading-5 text-muted-foreground">
                <Heart className="mt-1 size-3 shrink-0 text-primary" />
                <span>
                  <span className="font-medium text-foreground">숨은 감정</span>{" "}
                  {character.hiddenFeeling || "—"}
                </span>
              </p>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="mt-2 w-full"
                aria-label={`${character.name} 인물 수정`}
                onClick={(event) => onEditCharacter?.(character.id, event.currentTarget)}
              >
                인물 수정
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
