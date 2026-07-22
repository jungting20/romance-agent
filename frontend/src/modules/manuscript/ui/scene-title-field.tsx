import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface SceneTitleFieldProps {
  title: string;
  disabled: boolean;
  onCommit: (title: string) => void;
}

export function SceneTitleField({ title, disabled, onCommit }: SceneTitleFieldProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const [error, setError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const blurCommitRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (blurCommitRef.current !== null) {
        window.clearTimeout(blurCommitRef.current);
      }
    },
    [],
  );

  useLayoutEffect(() => {
    if (editing && !disabled) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [disabled, editing]);

  const cancel = () => {
    if (blurCommitRef.current !== null) {
      window.clearTimeout(blurCommitRef.current);
      blurCommitRef.current = null;
    }
    setDraft(title);
    setError(null);
    setEditing(false);
    setAnnouncement("장면 제목 수정을 취소했어요.");
  };

  const commit = () => {
    if (disabled) return;
    const normalized = draft.trim();
    if (!normalized) {
      setError("장면 제목을 입력해 주세요.");
      return;
    }
    onCommit(draft);
    setDraft(normalized);
    setError(null);
    setEditing(false);
    setAnnouncement("장면 제목을 저장할 준비가 되었어요.");
  };

  if (!editing) {
    return (
      <div className="mt-3 flex items-start gap-2">
        <h2 className="min-w-0 flex-1 font-heading text-3xl font-semibold">{title}</h2>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="장면 제목 수정"
          disabled={disabled}
          onClick={() => {
            setDraft(title);
            setError(null);
            setEditing(true);
          }}
        >
          <Pencil />
        </Button>
        {announcement && (
          <span role="status" aria-live="polite" className="sr-only">
            {announcement}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="mt-3">
      <Input
        ref={inputRef}
        aria-label="장면 제목"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? "scene-title-error" : undefined}
        value={draft}
        disabled={disabled}
        onChange={(event) => {
          setDraft(event.target.value);
          if (event.target.value.trim()) setError(null);
        }}
        onBlur={() => {
          blurCommitRef.current = window.setTimeout(() => {
            blurCommitRef.current = null;
            commit();
          }, 0);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commit();
          }
          if (event.key === "Escape") {
            event.preventDefault();
            cancel();
          }
        }}
        className="h-auto px-0 py-0 font-heading text-3xl font-semibold"
      />
      {error && (
        <p id="scene-title-error" role="alert" className="mt-2 text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
