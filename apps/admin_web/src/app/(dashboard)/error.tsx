"use client";

import { Button } from "@/components/ui/button";

export default function DashboardError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert" data-testid="page-error" className="mx-auto flex max-w-md flex-col items-center gap-3 rounded-lg border border-border bg-card p-10 text-center">
      <h2 className="text-lg font-semibold">This page could not be loaded</h2>
      <p className="text-sm text-muted-foreground">
        The admin API did not answer as expected.{error.digest ? ` Reference: ${error.digest}` : ""}
      </p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
