import { SignOutButton } from "@/components/layout/sign-out-button";

export function Header({ adminName }: { adminName: string }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-card px-6">
      <span className="text-sm font-semibold text-primary md:hidden">ZURUV</span>
      <h1 className="hidden text-sm font-medium text-muted-foreground md:block">Admin</h1>
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted-foreground">{adminName}</span>
        <SignOutButton />
      </div>
    </header>
  );
}
