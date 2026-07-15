import { Heart, MapPin } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { StoryBible } from "@/modules/story-bible";

interface StoryContextPanelProps {
  bible: StoryBible;
  mode: "characters" | "world";
  onEditWorld?: () => void;
}

const worldKindLabels = { place: "장소", object: "사물", rule: "규칙" } as const;

export function StoryContextPanel({ bible, mode, onEditWorld }: StoryContextPanelProps) {
  if (mode === "world") {
    return (
      <div className="h-full p-4">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">세계관</h2>
          <Button type="button" size="sm" variant="outline" onClick={onEditWorld}>
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
      <h2 className="mb-4 text-sm font-semibold">등장인물</h2>
      <div className="space-y-3">
        {bible.characters.map((character, index) => (
          <Card key={character.id} className="gap-2 border-sidebar-border bg-card py-3 shadow-none">
            <CardContent className="px-3">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="grid size-7 place-items-center rounded-full bg-secondary text-xs font-semibold text-primary">
                    {character.name.slice(0, 1)}
                  </span>
                  <p className="text-xs font-semibold">{character.name}</p>
                </div>
                <Badge variant="outline" className="text-[9px]">
                  {index === 0 ? "주인공" : "상대역"}
                </Badge>
              </div>
              <p className="flex gap-1.5 text-[11px] leading-5 text-muted-foreground">
                <Heart className="mt-1 size-3 shrink-0 text-primary" />
                {character.hiddenFeeling}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
