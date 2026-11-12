export function DetailGrid({ children }: { children: React.ReactNode }) {
  return <dl className="grid gap-x-8 gap-y-4 p-6 sm:grid-cols-2 lg:grid-cols-3">{children}</dl>;
}
export function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words text-sm">{children ?? "—"}</dd>
    </div>
  );
}
export function Mono({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-xs">{children}</span>;
}
