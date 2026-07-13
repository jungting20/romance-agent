import { ArrowUpRight, Clock3, Feather } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { Project } from "@/modules/projects";

interface ProjectCardProps {
  project: Project;
  tropeTitle: string;
}

export function ProjectCard({ project, tropeTitle }: ProjectCardProps) {
  return (
    <Link
      to={`/projects/${project.id}/write`}
      className="group block rounded-2xl focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <Card className="h-full overflow-hidden border-border/70 bg-card/90 py-0 shadow-[0_18px_60px_-42px_rgba(75,48,36,0.55)] transition duration-300 group-hover:-translate-y-1 group-hover:border-primary/30 group-hover:shadow-[0_22px_70px_-40px_rgba(139,80,59,0.5)]">
        <div className="relative h-38 overflow-hidden bg-[linear-gradient(135deg,#bea292_0%,#8f5f52_55%,#4e3934_100%)]">
          <div className="absolute inset-0 opacity-35 [background-image:radial-gradient(circle_at_25%_30%,white_0,transparent_23%),radial-gradient(circle_at_75%_70%,#e5b39b_0,transparent_27%)]" />
          <div className="absolute inset-0 grid place-items-center">
            <span className="grid size-14 place-items-center rounded-full border border-white/30 bg-white/10 text-white backdrop-blur-sm">
              <Feather className="size-6" />
            </span>
          </div>
          <Badge className="absolute top-4 left-4 border-white/20 bg-black/20 text-white backdrop-blur">
            {tropeTitle}
          </Badge>
        </div>
        <CardHeader className="pt-5">
          <CardTitle className="font-heading text-xl leading-tight">{project.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="line-clamp-2 min-h-11 text-sm leading-6 text-muted-foreground">
            {project.logline}
          </p>
        </CardContent>
        <CardFooter className="flex items-center justify-between border-t border-border/60 py-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Clock3 className="size-3.5" /> 최근 집필
          </span>
          <span className="flex items-center gap-1 font-medium text-primary opacity-0 transition group-hover:opacity-100">
            이어 쓰기 <ArrowUpRight className="size-3.5" />
          </span>
        </CardFooter>
      </Card>
    </Link>
  );
}
