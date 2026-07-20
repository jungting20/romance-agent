import { Link, Navigate, useNavigate, useSearch } from "@tanstack/react-router";
import { ArrowLeft, Heart } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ProjectSetupForm, useProjectSetup } from "@/features/create-project";
import { TROPE_TEMPLATES, type TropeTemplate } from "@/modules/story-design";
import { BrandMark } from "@/shared/ui/brand-mark";

export function SetupPage() {
  const { trope: tropeId } = useSearch({ from: "/new_/setup" });
  const trope = TROPE_TEMPLATES.find(({ id }) => id === tropeId);

  if (!trope) {
    return <Navigate to="/new" replace />;
  }

  return <SetupPageContent key={trope.id} trope={trope} />;
}

function SetupPageContent({ trope }: { trope: TropeTemplate }) {
  const navigate = useNavigate({ from: "/new/setup" });
  const setup = useProjectSetup({
    tropeId: trope.id,
    starterLogline: trope.starterLogline,
    onCreated: (projectId) =>
      navigate({
        to: "/projects/$projectId/write",
        params: { projectId },
      }),
  });

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

        <ProjectSetupForm setup={setup} />
      </main>
    </div>
  );
}
