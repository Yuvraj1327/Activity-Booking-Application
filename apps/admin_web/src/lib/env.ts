// NEXT_PUBLIC_* values are inlined at build time, so each must be referenced literally.
export const env = {
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
  // Only development falls back to the local backend; a production build must be configured.
  apiBaseUrl: (
    process.env.NEXT_PUBLIC_API_BASE_URL ?? (process.env.NODE_ENV === "production" ? "" : "http://localhost:8008/api/v1")
  ).replace(/\/+$/, ""),
} as const;

export const isSupabaseConfigured = Boolean(env.supabaseUrl && env.supabaseAnonKey && env.apiBaseUrl);
