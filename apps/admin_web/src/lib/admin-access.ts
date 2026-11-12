import "server-only";
import { env } from "@/lib/env";
import { getServerSupabase } from "@/lib/supabase/server";

export type AdminProfile = { id: string; full_name: string; email: string | null; role: "admin" };

export type AdminAccess =
  | { kind: "ok"; admin: AdminProfile }
  | { kind: "not_configured" }
  | { kind: "signed_out" }
  | { kind: "mfa_required" }
  | { kind: "forbidden"; code: string }
  | { kind: "error"; message: string };

/**
 * The ONLY place that decides whether the current visitor is an administrator.
 *
 * 1. Supabase verifies the session (getUser() validates the token with the Auth server; the
 *    cookie alone is never trusted).
 * 2. The ZURUV API (`GET /admin/me`) checks, from the database, that the account exists, is
 *    active, has role "admin" and (when enabled) completed MFA. The browser cannot influence this.
 */
export async function getAdminAccess(): Promise<AdminAccess> {
  const supabase = await getServerSupabase();
  if (!supabase) return { kind: "not_configured" };

  const { data: userData, error } = await supabase.auth.getUser();
  if (error || !userData.user) return { kind: "signed_out" };
  const { data: sessionData } = await supabase.auth.getSession();
  const token = sessionData.session?.access_token;
  if (!token) return { kind: "signed_out" };

  let res: Response;
  try {
    res = await fetch(`${env.apiBaseUrl}/admin/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    return { kind: "error", message: "The ZURUV API is unreachable." };
  }

  if (res.ok) return { kind: "ok", admin: (await res.json()) as AdminProfile };
  const body = (await res.json().catch(() => null)) as { code?: string } | null;
  const code = body?.code ?? `HTTP_${res.status}`;
  if (res.status === 401) return { kind: "signed_out" };
  if (res.status === 403 && code === "MFA_REQUIRED") return { kind: "mfa_required" };
  if (res.status === 403) return { kind: "forbidden", code };
  return { kind: "error", message: "The ZURUV API returned an unexpected error." };
}
