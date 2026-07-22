import { FileText, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Manuscript } from "@/modules/manuscript";

interface SceneTreeProps {
  manuscript: Manuscript;
  onAdd: () => void;
  onSelect: (sceneId: string) => void;
  addDisabled: boolean;
}

export function SceneTree({ manuscript, onAdd, onSelect, addDisabled }: SceneTreeProps) {
  return (
    <div className="h-full p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold">원고 목차</h2>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label="새 장면 추가"
          disabled={addDisabled}
          onClick={onAdd}
        >
          <Plus />
        </Button>
      </div>
      <div className="space-y-1">
        {manuscript.scenes.map((scene) => (
          <button
            key={scene.id}
            type="button"
            aria-current={scene.id === manuscript.activeSceneId ? "true" : undefined}
            aria-label={`${scene.chapterNumber}장 ${scene.title}`}
            onClick={() => onSelect(scene.id)}
            className={cn(
              "flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2.5 text-left",
              scene.id === manuscript.activeSceneId &&
                "bg-sidebar-accent text-sidebar-accent-foreground",
            )}
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
