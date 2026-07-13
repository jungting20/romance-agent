import { ArrowRight, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useApp } from "@/app/state/app-provider";
import { ProjectCard } from "@/modules/projects/ui/project-card";
import { getTropeTemplate } from "@/modules/story-design";
import { AppHeader } from "@/shared/ui/app-header";

export function LibraryPage() {
  const { state } = useApp();

  return (
    <div className="min-h-svh bg-background">
      <AppHeader />
      <main className="mx-auto max-w-7xl px-6 py-12 lg:px-10 lg:py-18">
        <section className="relative mb-14 overflow-hidden rounded-[2rem] border border-border/70 bg-card px-7 py-10 shadow-[0_30px_100px_-65px_rgba(76,45,34,0.65)] md:px-12 md:py-14">
          <div className="pointer-events-none absolute -top-28 -right-24 size-80 rounded-full bg-primary/8 blur-3xl" />
          <div className="relative max-w-2xl">
            <p className="mb-4 text-xs font-semibold tracking-[0.22em] text-primary uppercase">
              Your writing room
            </p>
            <h1 className="font-heading text-4xl leading-[1.15] font-semibold tracking-tight md:text-5xl">
              다시, 이야기를 시작해 볼까요?
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-muted-foreground md:text-lg">
              관계의 첫 떨림부터 마지막 문장까지. 당신의 로맨스를 한곳에서 기획하고 써 내려가세요.
            </p>
            <Button className="mt-8 h-11 rounded-full px-5" size="lg" asChild>
              <Link to="/new" aria-label="새 작품 시작">
                <Plus data-icon="inline-start" />새 작품 시작
                <ArrowRight data-icon="inline-end" />
              </Link>
            </Button>
          </div>
        </section>

        <section>
          <div className="mb-6 flex items-end justify-between">
            <div>
              <p className="text-xs font-semibold tracking-[0.18em] text-primary uppercase">
                Library
              </p>
              <h2 className="mt-2 font-heading text-2xl font-semibold">내 작품</h2>
            </div>
            <p className="text-sm text-muted-foreground">
              {state.projects.length}개의 이야기가 기다리고 있어요
            </p>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {state.projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                tropeTitle={getTropeTemplate(project.tropeId).title}
              />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
