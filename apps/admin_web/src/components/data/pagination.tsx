import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { href, type SearchParams } from "@/lib/query";
import { cn } from "@/lib/utils";

export function Pagination({ path, params, page, hasMore, shown, pageParam = "page", anchor }: { path: string; params: SearchParams; page: number; hasMore: boolean; shown: number; pageParam?: string; anchor?: string }) {
  if (page === 1 && !hasMore) return null;
  const btn = "inline-flex h-8 items-center gap-1 rounded-md border border-border px-3 text-sm";
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between border-t border-border px-4 py-3 text-sm text-muted-foreground">
      <span>
        Page {page} · {shown} shown
      </span>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link rel="prev" className={cn(btn, "hover:bg-muted")} href={href(path, params, { [pageParam]: page - 1 > 1 ? String(page - 1) : undefined }) + (anchor ? `#${anchor}` : "")}>
            <ChevronLeft className="size-4" aria-hidden /> Previous
          </Link>
        ) : (
          <span className={cn(btn, "opacity-40")} aria-disabled="true"><ChevronLeft className="size-4" aria-hidden /> Previous</span>
        )}
        {hasMore ? (
          <Link rel="next" className={cn(btn, "hover:bg-muted")} href={href(path, params, { [pageParam]: String(page + 1) }) + (anchor ? `#${anchor}` : "")}>
            Next <ChevronRight className="size-4" aria-hidden />
          </Link>
        ) : (
          <span className={cn(btn, "opacity-40")} aria-disabled="true">Next <ChevronRight className="size-4" aria-hidden /></span>
        )}
      </div>
    </nav>
  );
}
