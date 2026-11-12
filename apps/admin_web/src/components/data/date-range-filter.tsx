import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/format";
import { href, PRESETS, type Range, type SearchParams } from "@/lib/query";
import { cn } from "@/lib/utils";

/** Today / 7 days / 30 days / this month / custom. Pure links and a GET form: no client state. */
export function DateRangeFilter({ path, params, range }: { path: string; params: SearchParams; range: Range }) {
  const keep = { from: undefined, to: undefined, range: undefined, page: undefined };
  return (
    <div className="flex flex-wrap items-end gap-3" data-testid="date-range">
      <div role="group" aria-label="Date range" className="inline-flex rounded-lg border border-border bg-card p-1">
        {PRESETS.map((p) => (
          <Link
            key={p.key}
            href={href(path, params, { ...keep, range: p.key })}
            aria-current={range.preset === p.key ? "true" : undefined}
            className={cn("rounded-md px-3 py-1.5 text-sm", range.preset === p.key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}
          >
            {p.label}
          </Link>
        ))}
      </div>
      <form method="get" action={path} className="flex items-end gap-2">
        {Object.entries(params)
          .filter(([k, v]) => !["from", "to", "range", "page"].includes(k) && typeof v === "string")
          .map(([k, v]) => <input key={k} type="hidden" name={k} value={v as string} />)}
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          From
          <Input type="date" name="from" defaultValue={range.preset === "custom" ? range.from : ""} required className="w-40" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          To
          <Input type="date" name="to" defaultValue={range.preset === "custom" ? range.to : ""} required className="w-40" />
        </label>
        <Button type="submit" variant="outline" size="sm" className="h-10">Custom range</Button>
      </form>
      <p className="pb-2 text-xs text-muted-foreground">
        Showing {formatDate(range.from)} – {formatDate(range.to)}
      </p>
    </div>
  );
}
