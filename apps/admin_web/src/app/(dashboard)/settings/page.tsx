import { PageHeader } from "@/components/data/page-header";
import { SettingsView } from "@/components/settings/settings-view";
import { adminGet, safe } from "@/lib/admin-api";
import { getAdminAccess } from "@/lib/admin-access";
import { env } from "@/lib/env";
import { getServerSupabase } from "@/lib/supabase/server";
import type { ApiVersion, MyProfile, NotificationPreferences } from "@/lib/types";

export const metadata = { title: "Settings" };
export const dynamic = "force-dynamic";

async function platformInfo(): Promise<{ api: ApiVersion | null; environment: string | null; database: string | null }> {
  // /health lives at the server root, outside the versioned prefix.
  const root = env.apiBaseUrl.replace(/\/api\/v1$/, "");
  const [v, h] = await Promise.all([
    fetch(`${env.apiBaseUrl}/version`, { cache: "no-store" }).then((r) => (r.ok ? (r.json() as Promise<ApiVersion>) : null)).catch(() => null),
    fetch(`${root}/health`, { cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<{ environment?: string; database?: { status?: string } }>) : null))
      .catch(() => null),
  ]);
  return { api: v, environment: h?.environment ?? null, database: h?.database?.status ?? null };
}

export default async function SettingsPage() {
  const access = await getAdminAccess();
  const email = access.kind === "ok" ? access.admin.email : null;

  const [profile, prefs, platform] = await Promise.all([
    safe(adminGet<MyProfile>("/profiles/me")),
    safe(adminGet<NotificationPreferences>("/notifications/preferences")),
    platformInfo(),
  ]);

  // Profile photos live in the private bucket: show a short-lived signed URL.
  let avatarUrl: string | null = null;
  if (profile.ok && profile.data.avatar_path) {
    const supabase = await getServerSupabase();
    const { data } = (await supabase?.storage.from("profile-images").createSignedUrl(profile.data.avatar_path, 3600)) ?? { data: null };
    avatarUrl = data?.signedUrl ?? null;
  }

  return (
    <>
      <PageHeader title="Settings" description="Manage your profile, security, appearance and notifications." />
      <SettingsView
        profile={profile.ok ? profile.data : null}
        profileError={profile.ok ? null : profile.error.message}
        email={profile.ok ? profile.data.email ?? email : email}
        avatarUrl={avatarUrl}
        prefs={prefs.ok ? prefs.data : null}
        prefsError={prefs.ok ? null : prefs.error.message}
        platform={platform}
        apiHost={env.apiBaseUrl ? new URL(env.apiBaseUrl).host : ""}
      />
    </>
  );
}
