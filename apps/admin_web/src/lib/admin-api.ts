import "server-only";
import { redirect } from "next/navigation";
import { env } from "@/lib/env";
import { getVerifiedSession } from "@/lib/session";

/** Error from the ZURUV API as seen by a server component / action. */
export class AdminApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "AdminApiError";
  }
}

type Query = Record<string, string | number | boolean | undefined | null>;

function qs(query: Query = {}): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function token(): Promise<string> {
  const session = await getVerifiedSession(); // verified once per request
  if (session.kind !== "ok") redirect("/login");
  return session.token;
}

/**
 * Calls the ZURUV API as the signed-in admin. The API decides everything: this wrapper only sends
 * the verified session token, and routes 401/403 to the right screen.
 */
export async function adminRequest(path: string, init: RequestInit & { query?: Query; raw?: boolean } = {}): Promise<Response> {
  const { query, raw, headers, ...rest } = init;
  const t = await token();
  let res: Response;
  try {
    res = await fetch(`${env.apiBaseUrl}${path}${qs(query)}`, {
      ...rest,
      headers: { ...(headers as Record<string, string>), Authorization: `Bearer ${t}` },
      cache: "no-store",
    });
  } catch {
    throw new AdminApiError(0, "NETWORK_ERROR", "The ZURUV API is unreachable.");
  }
  if (res.ok || raw) return res;
  const body = (await res.json().catch(() => null)) as { code?: string; message?: string } | null;
  const code = body?.code ?? `HTTP_${res.status}`;
  if (res.status === 401) redirect("/login");
  if (res.status === 403 && code === "MFA_REQUIRED") redirect("/mfa");
  if (res.status === 403 && (code === "INSUFFICIENT_ROLE" || code === "ACCOUNT_SUSPENDED")) redirect("/unauthorized");
  throw new AdminApiError(res.status, code, body?.message ?? res.statusText);
}

export async function adminGet<T>(path: string, query?: Query): Promise<T> {
  return (await adminRequest(path, { query })).json() as Promise<T>;
}

export async function adminSend<T>(method: "POST" | "PATCH" | "PUT", path: string, body?: unknown): Promise<T> {
  const res = await adminRequest(path, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return (res.status === 204 ? undefined : await res.json().catch(() => undefined)) as T;
}

/** Fetch that turns a failed read into a value the page can render as an error state. */
export async function safe<T>(p: Promise<T>): Promise<{ ok: true; data: T } | { ok: false; error: AdminApiError }> {
  try {
    return { ok: true, data: await p };
  } catch (e) {
    if (e instanceof AdminApiError) return { ok: false, error: e };
    // redirect() throws a control-flow error that must propagate
    throw e;
  }
}
