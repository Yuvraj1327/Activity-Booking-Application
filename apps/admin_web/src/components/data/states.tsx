import { AlertTriangle, Inbox } from "lucide-react";
import { Alert } from "@/components/ui/alert";

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center" data-testid="empty-state">
      <span className="flex size-12 items-center justify-center rounded-full bg-primary-tint text-primary">
        <Inbox className="size-6" aria-hidden />
      </span>
      <p className="font-medium">{title}</p>
      {description && <p className="max-w-sm text-sm text-muted-foreground">{description}</p>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <Alert className="flex items-start gap-2" data-testid="error-state">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
      <span>{message}</span>
    </Alert>
  );
}

export function UnavailableNote({ what, depends }: { what: string; depends: string }) {
  return (
    <p className="text-sm text-muted-foreground" data-testid="unavailable-note">
      <span className="font-medium text-foreground">{what}:</span> not available — waiting for an approved rule ({depends}).
    </p>
  );
}
