import { Link } from "@tanstack/react-router";
import { Feather } from "lucide-react";

export function BrandMark() {
  return (
    <Link className="flex items-center gap-2 text-foreground" to="/" aria-label="Muse 작품 서재">
      <span className="grid size-9 place-items-center rounded-full bg-primary text-primary-foreground shadow-sm">
        <Feather className="size-4" />
      </span>
      <span className="font-heading text-xl font-semibold tracking-tight">Muse</span>
    </Link>
  );
}
