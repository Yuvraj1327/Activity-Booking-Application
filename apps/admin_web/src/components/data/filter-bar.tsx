import Link from "next/link";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { one, type SearchParams } from "@/lib/query";
import { titleCase } from "@/lib/format";

export type FilterField =
  | { kind: "search"; name: string; placeholder: string }
  | { kind: "select"; name: string; label: string; options: string[] | { value: string; label: string }[] }
  | { kind: "date"; name: string; label: string };

/** A plain GET form: works without JavaScript, and every filter lives in the URL. */
export function FilterBar({ path, params, fields }: { path: string; params: SearchParams; fields: FilterField[] }) {
  const active = fields.some((f) => one(params, f.name));
  return (
    <form method="get" action={path} role="search" className="flex flex-wrap items-end gap-3 border-b border-border p-4">
      {fields.map((f) => {
        const value = one(params, f.name) ?? "";
        if (f.kind === "search")
          return (
            <div key={f.name} className="relative min-w-56 flex-1">
              <Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" aria-hidden />
              <Input name={f.name} defaultValue={value} placeholder={f.placeholder} aria-label={f.placeholder} className="pl-9" maxLength={100} />
            </div>
          );
        if (f.kind === "date")
          return (
            <label key={f.name} className="flex flex-col gap-1 text-xs text-muted-foreground">
              {f.label}
              <Input type="date" name={f.name} defaultValue={value} className="h-10 w-40" />
            </label>
          );
        const opts = f.options.map((o) => (typeof o === "string" ? { value: o, label: titleCase(o) } : o));
        return (
          <label key={f.name} className="flex flex-col gap-1 text-xs text-muted-foreground">
            {f.label}
            <Select name={f.name} defaultValue={value} className="w-44">
              <option value="">All</option>
              {opts.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </Select>
          </label>
        );
      })}
      <Button type="submit" size="sm" className="h-10">Apply</Button>
      {active && (
        <Link href={path} className="inline-flex h-10 items-center px-2 text-sm text-primary hover:underline">Clear</Link>
      )}
    </form>
  );
}
