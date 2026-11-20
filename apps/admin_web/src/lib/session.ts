import "server-only";
import { cache } from "react";
import { getServerSupabase } from "@/lib/supabase/server";

export type VerifiedSession = { kind: "ok"; token: string } | { kind: "not_configured" } | { kind: "signed_out" };

/**
 * The signed-in user's access token, with its signature and expiry verified (the cookie alone is
 * never trusted). `getClaims()` checks the JWT locally against Supabase's cached public keys, with no
 * network round trip; projects on the legacy shared secret fall back to asking the Auth server.
 * The ZURUV API re-verifies the token and the admin role from the database on every call, so this
 * is only the first gate. Wrapped in React `cache` so it runs once per request.
 */
export const getVerifiedSession = cache(async (): Promise<VerifiedSession> => {
  const supabase = await getServerSupabase();
  if (!supabase) return { kind: "not_configured" };
  const { data: claims, error } = await supabase.auth.getClaims();
  if (error || !claims?.claims) return { kind: "signed_out" };
  const { data } = await supabase.auth.getSession();
  return data.session ? { kind: "ok", token: data.session.access_token } : { kind: "signed_out" };
});
