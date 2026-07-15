import { Link } from "@tanstack/react-router";
import { BookOpenText, Settings2 } from "lucide-react";

import { Button } from "@/components/ui/button";

import { BrandMark } from "./brand-mark";

export function AppHeader() {
  return (
    <header className="border-b border-border/70 bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-18 max-w-7xl items-center justify-between px-6 lg:px-10">
        <BrandMark />
        <nav className="flex items-center gap-1" aria-label="주요 메뉴">
          <Button variant="ghost" asChild>
            <Link to="/">
              <BookOpenText data-icon="inline-start" />내 작품
            </Link>
          </Button>
          <Button variant="ghost" size="icon" aria-label="설정">
            <Settings2 />
          </Button>
        </nav>
      </div>
    </header>
  );
}
