import { env } from "@/lib/env";
import { getSupabaseClient } from "@/lib/supabase/client";

/** Error shape returned by the ZURUV API (docs/SYSTEM_ARCHITECTURE.md section 18). */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: unknown = null,
    public requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Options = Omit<RequestInit, "body"> & { body?: unknown; auth?: boolean };

export async function apiFetch<T>(path: string, { body, auth = true, headers, ...init }: Options = {}): Promise<T> {
  const h = new Headers(headers);
  if (body !== undefined) h.set("Content-Type", "application/json");
  if (auth) {
    const { data } = (await getSupabaseClient()?.auth.getSession()) ?? { data: null };
    if (data?.session) h.set("Authorization", `Bearer ${data.session.access_token}`);
  }

  let res: Response;
  try {
    res = await fetch(`${env.apiBaseUrl}${path}`, {
      ...init,
      headers: h,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Cannot reach the server. Check your connection.");
  }

  if (!res.ok) {
    const e = await res.json().catch(() => null);
    throw new ApiError(
      res.status,
      e?.code ?? `HTTP_${res.status}`,
      e?.message ?? res.statusText,
      e?.details ?? null,
      e?.request_id ?? null,
    );
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}
