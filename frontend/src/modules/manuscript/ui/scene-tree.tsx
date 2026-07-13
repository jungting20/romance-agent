import { FileText, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Manuscript } from "@/modules/manuscript";

interface SceneTreeProps {
  manuscript: Manuscript;
}

export function SceneTree({ manuscript }: SceneTreeProps) {
  return (
    <div className="h-full p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold">원고 목차</h2>
        <Button variant="ghost" size="icon-xs" aria-label="새 장면 추가" disabled>
          <Plus />
        </Button>
      </div>
      <div className="space-y-1">
        <p className="px-2 py-1 text-[10px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
          1부 · 다시 만난 계절
        </p>
        {manuscript.scenes.map((scene) => (
          <button
            key={scene.id}
            type="button"
            className="flex w-full items-start gap-2.5 rounded-lg bg-sidebar-accent px-2.5 py-2.5 text-left text-sidebar-accent-foreground"
          >
            <FileText className="mt-0.5 size-4 shrink-0 text-primary" />
            <span>
              <span className="block text-xs font-medium">{scene.chapterNumber}장</span>
              <span className="mt-0.5 block text-[11px] text-muted-foreground">{scene.title}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
