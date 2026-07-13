import { type FormEvent, useState } from "react";
import { ArrowLeft, ArrowRight, Heart, Sparkles } from "lucide-react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { useApp } from "@/app/state/app-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { TROPE_TEMPLATES } from "@/modules/story-design";
import { BrandMark } from "@/shared/ui/brand-mark";

export function SetupPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { createProject } = useApp();
  const tropeId = searchParams.get("trope");
  const trope = TROPE_TEMPLATES.find(({ id }) => id === tropeId);
  const [title, setTitle] = useState("");
  const [logline, setLogline] = useState(trope?.starterLogline ?? "");
  const [firstName, setFirstName] = useState("서윤");
  const [secondName, setSecondName] = useState("도현");

  if (!trope) {
    return <Navigate to="/new" replace />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trope) {
      return;
    }
    const projectId = createProject({
      title,
      logline,
      tropeId: trope.id,
      protagonistNames: [firstName, secondName],
    });
    void navigate(`/projects/${projectId}/write`);
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
            <form className="space-y-7" onSubmit={handleSubmit}>
              <div className="space-y-2.5">
                <Label htmlFor="project-title">작품 제목</Label>
                <Input
                  id="project-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="아직 제목이 없어도 괜찮아요"
                  required
                  className="h-11 bg-background/60"
                />
              </div>
              <div className="space-y-2.5">
                <Label htmlFor="project-logline">한 줄 아이디어</Label>
                <Textarea
                  id="project-logline"
                  value={logline}
                  onChange={(event) => setLogline(event.target.value)}
                  rows={4}
                  required
                  className="resize-none bg-background/60 leading-6"
                />
                <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
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
                      value={firstName}
                      onChange={(event) => setFirstName(event.target.value)}
                      required
                      className="h-11 bg-background/60"
                    />
                  </div>
                  <div className="space-y-2.5">
                    <Label htmlFor="second-protagonist">두 번째 주인공</Label>
                    <Input
                      id="second-protagonist"
                      value={secondName}
                      onChange={(event) => setSecondName(event.target.value)}
                      required
                      className="h-11 bg-background/60"
                    />
                  </div>
                </div>
              </div>
              <Button type="submit" size="lg" className="h-11 w-full rounded-xl">
                작업 공간 열기 <ArrowRight data-icon="inline-end" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
