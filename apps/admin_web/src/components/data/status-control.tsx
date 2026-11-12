"use client";

import { useActionState, useRef } from "react";
import { changeAccountStatus, type ActionState } from "@/app/actions";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

/** Suspend / reactivate with a mandatory reason. The change is made and audited by the API. */
export function StatusControl({ role, id, name, status }: { role: "owner" | "customer"; id: string; name: string; status: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [state, action, pending] = useActionState<ActionState, FormData>(changeAccountStatus, null);
  const target = status === "suspended" ? "active" : "suspended";
  const verb = target === "suspended" ? "Suspend" : "Reactivate";
  return (
    <>
      <Button variant={target === "suspended" ? "outline" : "default"} size="sm" onClick={() => ref.current?.showModal()} data-testid="status-open">
        {verb} account
      </Button>
      <dialog ref={ref} aria-labelledby={`dlg-${id}`} className="m-auto w-full max-w-md rounded-xl border border-border p-0 shadow-xl backdrop:bg-black/40">
        <form action={action} className="space-y-4 p-6">
          <input type="hidden" name="role" value={role} />
          <input type="hidden" name="id" value={id} />
          <input type="hidden" name="status" value={target} />
          <h3 id={`dlg-${id}`} className="text-lg font-semibold">{verb} {name}?</h3>
          <p className="text-sm text-muted-foreground">
            {target === "suspended"
              ? "They will be refused on their next request. Existing bookings are not cancelled or refunded."
              : "They will be able to sign in and use the app again."}{" "}
            This is recorded in the audit log with your reason.
          </p>
          <div className="space-y-1.5">
            <Label htmlFor={`reason-${id}`}>Reason</Label>
            <Textarea id={`reason-${id}`} name="reason" required minLength={3} maxLength={300} placeholder="Why is this being changed?" />
          </div>
          {state && <Alert variant={state.ok ? "info" : "error"} data-testid="status-result">{state.message}</Alert>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => ref.current?.close()}>Close</Button>
            {!state?.ok && <Button type="submit" size="sm" disabled={pending} data-testid="status-confirm">{pending ? "Saving..." : verb}</Button>}
          </div>
        </form>
      </dialog>
    </>
  );
}
