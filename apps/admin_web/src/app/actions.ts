"use server";

import { revalidatePath } from "next/cache";
import { AdminApiError, adminSend } from "@/lib/admin-api";

export type ActionState = { ok: boolean; message: string } | null;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Suspend / reactivate an owner or customer. The API enforces everything; this only forwards. */
export async function changeAccountStatus(_prev: ActionState, form: FormData): Promise<ActionState> {
  const role = String(form.get("role") ?? "");
  const id = String(form.get("id") ?? "");
  const status = String(form.get("status") ?? "");
  const reason = String(form.get("reason") ?? "").trim();
  if (!["owner", "customer"].includes(role) || !UUID.test(id) || !["active", "suspended"].includes(status)) {
    return { ok: false, message: "Invalid request." };
  }
  if (reason.length < 3) return { ok: false, message: "Please give a reason (at least 3 characters)." };
  try {
    const out = await adminSend<{ changed: boolean }>("PATCH", `/admin/${role}s/${id}/status`, { status, reason });
    revalidatePath(`/${role}s`);
    revalidatePath(`/${role}s/${id}`);
    revalidatePath("/audit");
    return { ok: true, message: out.changed ? "Account updated and recorded in the audit log." : "No change: the account already had that status." };
  } catch (e) {
    if (e instanceof AdminApiError) return { ok: false, message: e.message };
    throw e;
  }
}

export async function markNotificationRead(form: FormData): Promise<void> {
  const id = String(form.get("id") ?? "");
  if (!UUID.test(id)) return;
  await adminSend("POST", `/notifications/${id}/read`);
  revalidatePath("/notifications");
  revalidatePath("/", "layout");
}

export async function markAllNotificationsRead(): Promise<void> {
  await adminSend("POST", "/notifications/read-all");
  revalidatePath("/notifications");
  revalidatePath("/", "layout");
}
