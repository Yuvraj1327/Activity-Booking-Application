import { ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/card";

/** Shown instead of every page when the administrator exists but has not been given a role yet. */
export function NoRole({ name }: { name: string }) {
  return (
    <Card className="mx-auto mt-10 max-w-lg p-8 text-center" data-testid="no-role">
      <ShieldAlert className="mx-auto size-10 text-warning-foreground" aria-hidden />
      <h2 className="mt-4 text-xl font-semibold">No permissions yet</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        {name}, your administrator account is active but has no role assigned, so nothing in the console is available to you.
        Ask an administrator who can manage roles to assign one.
      </p>
    </Card>
  );
}
