import { ArrowRight, Handshake, HeartHandshake, RefreshCcw, Swords } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TROPE_TEMPLATES } from "@/modules/story-design";

const icons = {
  "rivals-to-lovers": Swords,
  "contract-romance": Handshake,
  reunion: RefreshCcw,
  "friends-to-lovers": HeartHandshake,
};

export function TropeSelector() {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      {TROPE_TEMPLATES.map((trope, index) => {
        const Icon = icons[trope.id as keyof typeof icons] ?? HeartHandshake;
        return (
          <Link
            key={trope.id}
            to={`/new/setup?trope=${trope.id}`}
            aria-label={`${trope.title} 선택`}
            className="group rounded-2xl focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <Card className="relative h-full overflow-hidden border-border/70 bg-card py-0 transition duration-300 group-hover:-translate-y-1 group-hover:border-primary/35 group-hover:shadow-xl">
              <div className="h-2 bg-primary/70" style={{ opacity: 0.55 + index * 0.1 }} />
              <CardHeader className="flex-row items-start gap-4 pt-6">
                <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-secondary text-primary">
                  <Icon className="size-5" />
                </span>
                <div className="space-y-1.5">
                  <CardTitle className="font-heading text-xl">{trope.title}</CardTitle>
                  <p className="text-sm text-muted-foreground">{trope.summary}</p>
                </div>
              </CardHeader>
              <CardContent className="pb-6">
                <div className="mb-5 flex flex-wrap gap-2">
                  {trope.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <p className="line-clamp-2 text-sm leading-6 text-muted-foreground">
                  {trope.starterLogline}
                </p>
                <span className="mt-5 flex items-center gap-1.5 text-sm font-semibold text-primary">
                  이 이야기로 시작{" "}
                  <ArrowRight className="size-4 transition group-hover:translate-x-1" />
                </span>
              </CardContent>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
