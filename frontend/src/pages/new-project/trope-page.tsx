import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { TropeSelector } from "@/modules/story-design/ui/trope-selector";
import { BrandMark } from "@/shared/ui/brand-mark";

export function TropePage() {
  return (
    <div className="min-h-svh bg-background">
      <header className="border-b border-border/70">
        <div className="mx-auto flex h-18 max-w-6xl items-center justify-between px-6 lg:px-10">
          <BrandMark />
          <Button variant="ghost" asChild>
            <Link to="/">
              <ArrowLeft data-icon="inline-start" />
              작품 서재
            </Link>
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-12 lg:px-10 lg:py-16">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <p className="mb-4 text-xs font-semibold tracking-[0.22em] text-primary uppercase">
            New story · Step 1
          </p>
          <h1 className="font-heading text-4xl font-semibold tracking-tight md:text-5xl">
            어떤 사랑을 쓰고 싶나요?
          </h1>
          <p className="mt-4 text-base leading-7 text-muted-foreground">
            관계의 시작점을 고르면 Muse가 첫 장면까지 함께 준비해 드릴게요.
          </p>
        </div>
        <TropeSelector />
      </main>
    </div>
  );
}
