"use server";

import { revalidatePath } from "next/cache";
import { AdminApiError, adminCall } from "@/lib/admin-api";

export type AdminActionState = { ok: boolean; message: string; data?: unknown } | null;

// Only the admin API, and only plain paths. The API still checks the admin's permission for each call
// with the admin's own token: this action adds no power, it only forwards.
const PATH = /^\/admin\/[A-Za-z0-9_\-/]+$/;
const METHODS = ["POST", "PATCH", "PUT", "DELETE"] as const;

export async function runAdminAction(_prev: AdminActionState, form: FormData): Promise<AdminActionState> {
  const method = String(form.get("method") ?? "") as (typeof METHODS)[number];
  const path = String(form.get("path") ?? "");
  const refresh = String(form.get("refresh") ?? "").split(",").filter((p) => p.startsWith("/") && !p.includes(".."));
  const idem = String(form.get("idempotency_key") ?? "");
  if (!METHODS.includes(method) || !PATH.test(path) || path.includes("..")) return { ok: false, message: "Invalid request." };
  let payload: unknown;
  try {
    const raw = String(form.get("payload") ?? "");
    payload = raw ? JSON.parse(raw) : undefined;
  } catch {
    return { ok: false, message: "Invalid request." };
  }
  try {
    const data = await adminCall<unknown>(method, path, payload, idem ? { "Idempotency-Key": idem } : {});
    for (const p of refresh) revalidatePath(p);
    revalidatePath("/audit");
    return { ok: true, message: String(form.get("success") ?? "Done. The change is recorded in the audit log."), data };
  } catch (e) {
    if (e instanceof AdminApiError) return { ok: false, message: e.message };
    throw e;
  }
}
