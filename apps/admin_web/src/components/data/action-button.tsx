"use client";

import { useActionState, useId, useRef, useState } from "react";
import { runAdminAction, type AdminActionState } from "@/app/admin-actions";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export type Field = {
  name: string;
  label: string;
  type?: "text" | "textarea" | "number" | "money" | "select" | "checkbox" | "checks" | "date" | "datetime" | "list";
  required?: boolean;
  options?: { value: string; label: string }[];
  placeholder?: string;
  help?: string;
  defaultValue?: string | number | boolean | null;
  min?: number;
  max?: number;
  maxLength?: number;
  /** Send null (not omit) when left empty, for fields the API lets you clear. */
  emptyAsNull?: boolean;
};

type Props = {
  label: string;
  title?: string;
  description?: React.ReactNode;
  method?: "POST" | "PATCH" | "PUT" | "DELETE";
  path: string;
  fields?: Field[];
  /** Values always sent (ids etc.). */
  fixed?: Record<string, unknown>;
  submitLabel?: string;
  variant?: "default" | "outline";
  danger?: boolean;
  size?: "default" | "sm";
  refresh?: string[];
  idempotent?: boolean;
  success?: string;
  testId?: string;
  disabled?: boolean;
  disabledReason?: string;
};

/** Rupees typed by a person -> integer paise. Returns NaN for anything that is not a plain amount. */
export function rupeesToPaise(v: string): number {
  if (!/^\d+(\.\d{1,2})?$/.test(v.trim())) return NaN;
  return Math.round(Number(v) * 100);
}

function build(fields: Field[], fd: FormData, fixed: Record<string, unknown>): { payload: Record<string, unknown>; error?: string } {
  const payload: Record<string, unknown> = { ...fixed };
  for (const f of fields) {
    if (f.type === "checks") {
      payload[f.name] = fd.getAll(f.name).map(String);
      continue;
    }
    const raw = fd.get(f.name);
    const text = raw === null ? "" : String(raw).trim();
    if (f.type === "checkbox") {
      payload[f.name] = raw === "on";
      continue;
    }
    if (!text) {
      if (f.required) return { payload, error: `${f.label} is required.` };
      if (f.emptyAsNull) payload[f.name] = null;
      continue;
    }
    switch (f.type) {
      case "money": {
        const p = rupeesToPaise(text);
        if (!Number.isFinite(p)) return { payload, error: `${f.label}: enter an amount like 250 or 250.50.` };
        payload[f.name] = p;
        break;
      }
      case "number": {
        const n = Number(text);
        if (!Number.isFinite(n)) return { payload, error: `${f.label} must be a number.` };
        payload[f.name] = n;
        break;
      }
      case "datetime":
        payload[f.name] = new Date(text).toISOString();
        break;
      case "list":
        payload[f.name] = text.split(/[\s,]+/).filter(Boolean);
        break;
      default:
        payload[f.name] = text;
    }
  }
  return { payload };
}

/** One button that opens a dialog, collects what the API needs, and calls it through the audited server action. */
export function ActionButton(p: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const id = useId();
  const [state, dispatch, pending] = useActionState<AdminActionState, FormData>(runAdminAction, null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [idem, setIdem] = useState(() => (typeof crypto !== "undefined" ? crypto.randomUUID() : String(Math.random())));
  const fields = p.fields ?? [];
  const done = state?.ok === true;

  const submit = (fd: FormData) => {
    const { payload, error } = build(fields, fd, p.fixed ?? {});
    if (error) return setClientError(error);
    setClientError(null);
    fd.set("method", p.method ?? "POST");
    fd.set("path", p.path);
    fd.set("payload", Object.keys(payload).length || (p.method ?? "POST") !== "DELETE" ? JSON.stringify(payload) : "");
    fd.set("refresh", (p.refresh ?? []).join(","));
    if (p.idempotent) fd.set("idempotency_key", idem);
    if (p.success) fd.set("success", p.success);
    dispatch(fd);
  };

  return (
    <>
      <Button
        variant={p.variant ?? "outline"}
        size={p.size ?? "sm"}
        onClick={() => dialog.current?.showModal()}
        disabled={p.disabled}
        title={p.disabled ? p.disabledReason : undefined}
        className={cn(p.danger && "border-destructive/50 text-destructive hover:bg-destructive/5")}
        data-testid={p.testId}
      >
        {p.label}
      </Button>
      <dialog
        ref={dialog}
        aria-labelledby={`${id}-t`}
        onClose={() => {
          if (done) setIdem(crypto.randomUUID());
        }}
        className="m-auto w-full max-w-lg rounded-xl border border-border p-0 shadow-xl backdrop:bg-black/40"
      >
        <form action={submit} className="max-h-[85vh] space-y-4 overflow-y-auto p-6">
          <h3 id={`${id}-t`} className="text-lg font-semibold">{p.title ?? p.label}</h3>
          {p.description && <div className="text-sm text-muted-foreground">{p.description}</div>}
          {fields.map((f) => (
            <div key={f.name} className={cn("space-y-1.5", f.type === "checkbox" && "flex items-center gap-2 space-y-0")}>
              {f.type !== "checkbox" && <Label htmlFor={`${id}-${f.name}`}>{f.label}{f.required && " *"}</Label>}
              {f.type === "checks" ? (
                <fieldset className="max-h-64 space-y-1 overflow-y-auto rounded-md border border-border p-3">
                  {f.options?.map((o) => (
                    <label key={o.value} className="flex items-start gap-2 text-sm">
                      <input type="checkbox" name={f.name} value={o.value} defaultChecked={String(f.defaultValue ?? "").split(",").includes(o.value)} className="mt-0.5 size-4" />
                      <span>{o.label}</span>
                    </label>
                  ))}
                </fieldset>
              ) : f.type === "textarea" ? (
                <Textarea id={`${id}-${f.name}`} name={f.name} required={f.required} maxLength={f.maxLength ?? 4000} placeholder={f.placeholder} defaultValue={String(f.defaultValue ?? "")} />
              ) : f.type === "select" ? (
                <Select id={`${id}-${f.name}`} name={f.name} required={f.required} defaultValue={String(f.defaultValue ?? "")}>
                  {!f.required && <option value="">—</option>}
                  {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </Select>
              ) : f.type === "checkbox" ? (
                <>
                  <input id={`${id}-${f.name}`} type="checkbox" name={f.name} defaultChecked={Boolean(f.defaultValue)} className="size-4" />
                  <Label htmlFor={`${id}-${f.name}`}>{f.label}</Label>
                </>
              ) : (
                <Input
                  id={`${id}-${f.name}`}
                  name={f.name}
                  required={f.required}
                  placeholder={f.placeholder}
                  defaultValue={f.defaultValue === null || f.defaultValue === undefined ? undefined : String(f.defaultValue)}
                  type={f.type === "date" ? "date" : f.type === "datetime" ? "datetime-local" : f.type === "number" ? "number" : "text"}
                  inputMode={f.type === "money" ? "decimal" : undefined}
                  min={f.min}
                  max={f.max}
                  maxLength={f.maxLength}
                />
              )}
              {f.help && <p className="text-xs text-muted-foreground">{f.help}</p>}
            </div>
          ))}
          {clientError && <Alert data-testid="action-error">{clientError}</Alert>}
          {state && <Alert variant={state.ok ? "info" : "error"} data-testid="action-result">{state.message}</Alert>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => dialog.current?.close()}>{done ? "Close" : "Cancel"}</Button>
            {!done && (
              <Button type="submit" size="sm" disabled={pending} data-testid="action-confirm" className={cn(p.danger && "bg-destructive text-white hover:bg-destructive/90")}>
                {pending ? "Saving..." : (p.submitLabel ?? p.label)}
              </Button>
            )}
          </div>
        </form>
      </dialog>
    </>
  );
}

/** The reason field nearly every sensitive action needs. */
export const REASON: Field = { name: "reason", label: "Reason", type: "textarea", required: true, maxLength: 300, placeholder: "Why is this being done? It is recorded in the audit log." };
export const OPTIONAL_REASON: Field = { ...REASON, required: false, label: "Note (optional)" };
