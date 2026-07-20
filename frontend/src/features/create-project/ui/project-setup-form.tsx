import { type FormEvent } from "react";
import { ArrowRight, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import type { ProjectSetupController } from "../use-project-setup";

export interface ProjectSetupFormProps {
  setup: ProjectSetupController;
}

export function ProjectSetupForm({ setup }: ProjectSetupFormProps) {
  const { draft, errors, isPending, updateField, submit } = setup;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit();
  }

  return (
    <Card className="border-border/70 bg-card px-1 py-2 shadow-[0_28px_90px_-55px_rgba(75,45,34,0.6)] sm:px-4 sm:py-5">
      <CardContent>
        <form
          aria-label="새 프로젝트 설정"
          aria-busy={isPending}
          className="space-y-7"
          onSubmit={handleSubmit}
        >
          <div className="space-y-2.5">
            <Label htmlFor="project-title">작품 제목</Label>
            <Input
              id="project-title"
              aria-describedby={errors.title ? "project-title-error" : undefined}
              aria-invalid={errors.title ? true : undefined}
              value={draft.title}
              onChange={(event) => updateField("title", event.target.value)}
              placeholder="작품 제목을 입력해 주세요"
              required
              disabled={isPending}
              className="h-11 bg-background/60"
            />
            {errors.title && (
              <p id="project-title-error" role="alert" className="text-sm text-destructive">
                {errors.title}
              </p>
            )}
          </div>

          <div className="space-y-2.5">
            <Label htmlFor="project-logline">한 줄 아이디어</Label>
            <Textarea
              id="project-logline"
              aria-describedby={
                errors.logline
                  ? "project-logline-help project-logline-error"
                  : "project-logline-help"
              }
              aria-invalid={errors.logline ? true : undefined}
              value={draft.logline}
              onChange={(event) => updateField("logline", event.target.value)}
              rows={4}
              disabled={isPending}
              className="resize-none bg-background/60 leading-6"
            />
            {errors.logline && (
              <p id="project-logline-error" role="alert" className="text-sm text-destructive">
                {errors.logline}
              </p>
            )}
            <p
              id="project-logline-help"
              className="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <Sparkles className="size-3.5 text-primary" /> 선택한 트로프에서 시작 문장을
              준비했어요.
            </p>
          </div>

          <fieldset>
            <legend className="mb-3 text-sm font-medium">두 주인공</legend>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2.5">
                <Label htmlFor="first-protagonist">첫 번째 주인공</Label>
                <Input
                  id="first-protagonist"
                  aria-describedby={
                    errors.protagonistNames ? "project-protagonists-error" : undefined
                  }
                  aria-invalid={errors.protagonistNames ? true : undefined}
                  value={draft.protagonistNames[0]}
                  onChange={(event) => updateField("firstProtagonist", event.target.value)}
                  required
                  disabled={isPending}
                  className="h-11 bg-background/60"
                />
              </div>
              <div className="space-y-2.5">
                <Label htmlFor="second-protagonist">두 번째 주인공</Label>
                <Input
                  id="second-protagonist"
                  aria-describedby={
                    errors.protagonistNames ? "project-protagonists-error" : undefined
                  }
                  aria-invalid={errors.protagonistNames ? true : undefined}
                  value={draft.protagonistNames[1]}
                  onChange={(event) => updateField("secondProtagonist", event.target.value)}
                  required
                  disabled={isPending}
                  className="h-11 bg-background/60"
                />
              </div>
            </div>
            {errors.protagonistNames && (
              <p
                id="project-protagonists-error"
                role="alert"
                className="mt-2 text-sm text-destructive"
              >
                {errors.protagonistNames}
              </p>
            )}
          </fieldset>

          {errors.form && (
            <p role="alert" className="text-sm text-destructive">
              {errors.form}
            </p>
          )}

          <Button
            type="submit"
            size="lg"
            disabled={isPending}
            className="h-11 w-full rounded-xl"
          >
            {isPending ? "작업 공간 여는 중" : "작업 공간 열기"}{" "}
            <ArrowRight data-icon="inline-end" />
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
