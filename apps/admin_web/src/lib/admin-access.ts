import "server-only";
import { env } from "@/lib/env";
import { cache } from "react";
import { getVerifiedSession } from "@/lib/session";

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
export const getAdminAccess = cache(async (): Promise<AdminAccess> => {
  const session = await getVerifiedSession();
  if (session.kind === "not_configured") return { kind: "not_configured" };
  if (session.kind !== "ok") return { kind: "signed_out" };
  const token = session.token;

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
});
