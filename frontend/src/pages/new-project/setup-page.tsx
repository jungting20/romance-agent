import { type FormEvent, useState } from "react";
import { ArrowLeft, ArrowRight, Heart, Sparkles } from "lucide-react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { ApiRequestError } from "@/app/infrastructure/api/api-client";
import type { TropeId } from "@/app/infrastructure/api/contracts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateProjectMutation } from "@/features/project-persistence";
import { TROPE_TEMPLATES } from "@/modules/story-design";
import { BrandMark } from "@/shared/ui/brand-mark";

export function SetupPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const createProject = useCreateProjectMutation();
  const tropeId = searchParams.get("trope");
  const selectedTropeId = isTropeId(tropeId) ? tropeId : undefined;
  const trope = TROPE_TEMPLATES.find(({ id }) => id === selectedTropeId);
  const [title, setTitle] = useState("");
  const [logline, setLogline] = useState(trope?.starterLogline ?? "");
  const [firstName, setFirstName] = useState("서윤");
  const [secondName, setSecondName] = useState("도현");
  const fieldErrors =
    createProject.error instanceof ApiRequestError && createProject.error.status === 422
      ? createProject.error.error.fieldErrors
      : [];
  const titleError = fieldErrors.find(({ path }) => path === "title")?.message;
  const loglineError = fieldErrors.find(({ path }) => path === "logline")?.message;
  const protagonistError = fieldErrors.find(({ path }) => path === "protagonistNames")?.message;
  const hasGenericError = createProject.isError && fieldErrors.length === 0;

  if (!trope) {
    return <Navigate to="/new" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trope || !selectedTropeId || createProject.isPending) {
      return;
    }

    try {
      const workspace = await createProject.mutateAsync({
        title,
        logline,
        tropeId: selectedTropeId,
        protagonistNames: [firstName, secondName],
      });
      void navigate(`/projects/${workspace.project.id}/write`);
    } catch {
      // The mutation state renders contract field errors or the generic failure state.
    }
  }

  return (
    <div className="min-h-svh bg-background">
      <header className="border-b border-border/70">
        <div className="mx-auto flex h-18 max-w-6xl items-center justify-between px-6 lg:px-10">
          <BrandMark />
          <Button variant="ghost" asChild>
            <Link to="/new">
              <ArrowLeft data-icon="inline-start" />
              트로프 다시 선택
            </Link>
          </Button>
        </div>
      </header>
      <main className="mx-auto grid max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[0.8fr_1.2fr] lg:px-10 lg:py-16">
        <aside className="lg:pt-12">
          <p className="mb-4 text-xs font-semibold tracking-[0.22em] text-primary uppercase">
            New story · Step 2
          </p>
          <h1 className="font-heading text-4xl leading-tight font-semibold tracking-tight">
            이야기의 첫 문장을 준비할게요
          </h1>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            지금은 알고 있는 만큼만 적어도 충분해요. 나머지는 집필하면서 함께 발견할 수 있습니다.
          </p>
          <Card className="mt-8 border-primary/20 bg-secondary/55 shadow-none">
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-primary text-primary-foreground">
                  <Heart className="size-4" />
                </span>
                <div>
                  <p className="text-xs text-muted-foreground">선택한 트로프</p>
                  <p className="font-heading text-lg font-semibold">{trope.title}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {trope.tags.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </aside>

        <Card className="border-border/70 bg-card px-1 py-2 shadow-[0_28px_90px_-55px_rgba(75,45,34,0.6)] sm:px-4 sm:py-5">
          <CardContent>
            <form
              aria-label="새 프로젝트 설정"
              aria-busy={createProject.isPending}
              className="space-y-7"
              onSubmit={handleSubmit}
            >
              <div className="space-y-2.5">
                <Label htmlFor="project-title">작품 제목</Label>
                <Input
                  id="project-title"
                  aria-describedby={titleError ? "project-title-error" : undefined}
                  aria-invalid={titleError ? true : undefined}
                  value={title}
                  onChange={(event) => {
                    createProject.reset();
                    setTitle(event.target.value);
                  }}
                  placeholder="아직 제목이 없어도 괜찮아요"
                  required
                  disabled={createProject.isPending}
                  className="h-11 bg-background/60"
                />
                {titleError && (
                  <p id="project-title-error" className="text-sm text-destructive">
                    {titleError}
                  </p>
                )}
              </div>
              <div className="space-y-2.5">
                <Label htmlFor="project-logline">한 줄 아이디어</Label>
                <Textarea
                  id="project-logline"
                  aria-describedby={loglineError ? "project-logline-error" : "project-logline-help"}
                  aria-invalid={loglineError ? true : undefined}
                  value={logline}
                  onChange={(event) => {
                    createProject.reset();
                    setLogline(event.target.value);
                  }}
                  rows={4}
                  required
                  disabled={createProject.isPending}
                  className="resize-none bg-background/60 leading-6"
                />
                {loglineError && (
                  <p id="project-logline-error" className="text-sm text-destructive">
                    {loglineError}
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
              <div>
                <p className="mb-3 text-sm font-medium">두 주인공</p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2.5">
                    <Label htmlFor="first-protagonist">첫 번째 주인공</Label>
                    <Input
                      id="first-protagonist"
                      aria-describedby={protagonistError ? "project-protagonists-error" : undefined}
                      aria-invalid={protagonistError ? true : undefined}
                      value={firstName}
                      onChange={(event) => {
                        createProject.reset();
                        setFirstName(event.target.value);
                      }}
                      required
                      disabled={createProject.isPending}
                      className="h-11 bg-background/60"
                    />
                  </div>
                  <div className="space-y-2.5">
                    <Label htmlFor="second-protagonist">두 번째 주인공</Label>
                    <Input
                      id="second-protagonist"
                      aria-describedby={protagonistError ? "project-protagonists-error" : undefined}
                      aria-invalid={protagonistError ? true : undefined}
                      value={secondName}
                      onChange={(event) => {
                        createProject.reset();
                        setSecondName(event.target.value);
                      }}
                      required
                      disabled={createProject.isPending}
                      className="h-11 bg-background/60"
                    />
                  </div>
                </div>
                {protagonistError && (
                  <p id="project-protagonists-error" className="mt-2 text-sm text-destructive">
                    {protagonistError}
                  </p>
                )}
              </div>
              {hasGenericError && (
                <p role="alert" className="text-sm text-destructive">
                  프로젝트를 만들지 못했어요. 잠시 후 다시 시도해 주세요.
                </p>
              )}
              <Button
                type="submit"
                size="lg"
                disabled={createProject.isPending}
                className="h-11 w-full rounded-xl"
              >
                {createProject.isPending ? "작업 공간 여는 중" : "작업 공간 열기"}{" "}
                <ArrowRight data-icon="inline-end" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}

function isTropeId(value: string | null): value is TropeId {
  return (
    value === "rivals-to-lovers" ||
    value === "contract-romance" ||
    value === "reunion" ||
    value === "friends-to-lovers"
  );
}
