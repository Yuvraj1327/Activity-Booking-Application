"use server";

import { revalidatePath } from "next/cache";
import { AdminApiError, adminSend } from "@/lib/admin-api";
import { getAdminAccess } from "@/lib/admin-access";
import type { MyProfile, NotificationPreferences } from "@/lib/types";

export type SettingsResult<T = undefined> = { ok: true; message: string; data?: T } | { ok: false; message: string };

const PHONE = /^\+[1-9][0-9]{6,14}$/;
const AVATAR_PATH = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/[A-Za-z0-9_-]{1,100}\.(jpg|jpeg|png|webp)$/i;

/**
 * Every action here re-checks that the caller is a signed-in, active, MFA-verified administrator,
 * and only ever talks to the "me" endpoints: the API derives WHOSE profile from the verified
 * token, so an admin can never change anyone else's data through this page.
 */
async function requireAdmin(): Promise<SettingsResult | null> {
  const access = await getAdminAccess();
  return access.kind === "ok" ? null : { ok: false, message: "Your session has expired. Please sign in again." };
}

function fail(e: unknown): SettingsResult {
  if (e instanceof AdminApiError) return { ok: false, message: e.message };
  throw e; // redirect() control flow and unexpected errors propagate
}

export async function updateProfile(input: { full_name: string; phone: string }): Promise<SettingsResult<MyProfile>> {
  const denied = await requireAdmin();
  if (denied) return denied;
  const full_name = input.full_name.trim();
  const phone = input.phone.trim();
  if (full_name.length < 1 || full_name.length > 120) return { ok: false, message: "Name must be 1 to 120 characters." };
  if (phone && !PHONE.test(phone)) return { ok: false, message: "Phone must be in international format, e.g. +919876543210." };
  try {
    const profile = await adminSend<MyProfile>("PATCH", "/profiles/me", { full_name, phone: phone || null });
    revalidatePath("/", "layout"); // header shows the name
    return { ok: true, message: "Profile saved.", data: profile };
  } catch (e) {
    return fail(e);
  }
}

/** Saves (or clears with null) the storage path of the profile photo already uploaded by the browser. */
export async function saveAvatarPath(path: string | null): Promise<SettingsResult<MyProfile>> {
  const denied = await requireAdmin();
  if (denied) return denied;
  if (path !== null && !AVATAR_PATH.test(path)) return { ok: false, message: "Invalid image path." };
  try {
    const profile = await adminSend<MyProfile>("PATCH", "/profiles/me", { avatar_path: path });
    revalidatePath("/", "layout");
    return { ok: true, message: path ? "Profile photo updated." : "Profile photo removed.", data: profile };
  } catch (e) {
    return fail(e);
  }
}

export async function savePreferences(prefs: Partial<NotificationPreferences>): Promise<SettingsResult<NotificationPreferences>> {
  const denied = await requireAdmin();
  if (denied) return denied;
  try {
    const out = await adminSend<NotificationPreferences>("PUT", "/notifications/preferences", prefs);
    return { ok: true, message: "Notification preferences saved.", data: out };
  } catch (e) {
    return fail(e);
  }
}
