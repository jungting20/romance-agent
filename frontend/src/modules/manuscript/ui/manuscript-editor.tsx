import { forwardRef, type ChangeEvent, type SyntheticEvent } from "react";

import { Textarea } from "@/components/ui/textarea";
import type { Scene, TextRange } from "@/modules/manuscript";

import { SceneTitleField } from "./scene-title-field";

interface ManuscriptEditorProps {
  scene: Scene;
  titleEditingDisabled: boolean;
  onTitleCommit: (title: string) => void;
  onChange: (content: string) => void;
  onSelectionChange: (range: TextRange) => void;
}

export const ManuscriptEditor = forwardRef<HTMLTextAreaElement, ManuscriptEditorProps>(
  function ManuscriptEditor(
    { scene, titleEditingDisabled, onTitleCommit, onChange, onSelectionChange },
    ref,
  ) {
    function captureSelection(event: SyntheticEvent<HTMLTextAreaElement>) {
      onSelectionChange({
        start: event.currentTarget.selectionStart,
        end: event.currentTarget.selectionEnd,
      });
    }

    return (
      <section className="mx-auto min-h-[calc(100svh-7rem)] max-w-3xl rounded-xl border border-[#ded2c6] bg-[#fffdf9] px-7 py-10 shadow-[0_24px_75px_-48px_rgba(58,40,31,0.7)] md:px-14 md:py-14">
        <p className="text-xs tracking-[0.16em] text-muted-foreground uppercase">
          Chapter {scene.chapterNumber.toString().padStart(2, "0")}
        </p>
        <SceneTitleField
          key={scene.id}
          title={scene.title}
          disabled={titleEditingDisabled}
          onCommit={onTitleCommit}
        />
        <Textarea
          ref={ref}
          aria-label="원고 본문"
          value={scene.content}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => {
            onChange(event.target.value);
            captureSelection(event);
          }}
          onSelect={captureSelection}
          onClick={captureSelection}
          onKeyUp={captureSelection}
          className="mt-8 min-h-[55svh] resize-none rounded-none border-0 bg-transparent p-0 font-heading text-[1.08rem] leading-9 shadow-none focus-visible:ring-0"
        />
      </section>
    );
  },
);
