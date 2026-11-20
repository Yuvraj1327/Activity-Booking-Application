"use client";

import { Bell, Info, Lock, Palette, ShieldCheck, User } from "lucide-react";
import { useSyncExternalStore } from "react";
import { AboutSection, type PlatformInfo } from "@/components/settings/about-section";
import { AccountSection } from "@/components/settings/account-section";
import { AppearanceSection } from "@/components/settings/appearance-section";
import { NotificationsSection } from "@/components/settings/notifications-section";
import { ProfileSection } from "@/components/settings/profile-section";
import { SecuritySection } from "@/components/settings/security-section";
import { Alert } from "@/components/ui/alert";
import type { MyProfile, NotificationPreferences } from "@/lib/types";
import { cn } from "@/lib/utils";

const SECTIONS = [
  { id: "profile", label: "Profile", icon: User },
  { id: "account", label: "Account", icon: Lock },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "security", label: "Security", icon: ShieldCheck },
  { id: "about", label: "About", icon: Info },
] as const;
type SectionId = (typeof SECTIONS)[number]["id"];

const HASH_EVENT = "zuruv-settings-hash";
function subscribeHash(cb: () => void) {
  window.addEventListener("hashchange", cb);
  window.addEventListener(HASH_EVENT, cb);
  return () => {
    window.removeEventListener("hashchange", cb);
    window.removeEventListener(HASH_EVENT, cb);
  };
}

export function SettingsView(props: {
  profile: MyProfile | null;
  profileError: string | null;
  email: string | null;
  avatarUrl: string | null;
  prefs: NotificationPreferences | null;
  prefsError: string | null;
  platform: PlatformInfo;
  apiHost: string;
}) {
  // The active section lives in the URL hash so /settings#security deep-links work.
  const hash = useSyncExternalStore(subscribeHash, () => window.location.hash.slice(1), () => "");
  const active: SectionId = SECTIONS.some((x) => x.id === hash) ? (hash as SectionId) : "profile";
  const select = (id: SectionId) => {
    history.replaceState(null, "", `#${id}`);
    window.dispatchEvent(new Event(HASH_EVENT));
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <nav aria-label="Settings sections" className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
        {SECTIONS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => select(id)}
            aria-current={active === id ? "page" : undefined}
            className={cn(
              "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium",
              active === id ? "bg-primary-tint text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-[18px]" aria-hidden />
            {label}
          </button>
        ))}
      </nav>

      <div className="min-w-0 max-w-3xl space-y-6">
        {active === "profile" &&
          (props.profile ? (
            <ProfileSection profile={props.profile} email={props.email} avatarUrl={props.avatarUrl} />
          ) : (
            <Alert>Could not load your profile{props.profileError ? `: ${props.profileError}` : "."}</Alert>
          ))}
        {active === "account" && <AccountSection email={props.email} profile={props.profile} />}
        {active === "appearance" && <AppearanceSection />}
        {active === "notifications" &&
          (props.prefs ? (
            <NotificationsSection initial={props.prefs} />
          ) : (
            <Alert>Could not load notification preferences{props.prefsError ? `: ${props.prefsError}` : "."}</Alert>
          ))}
        {active === "security" && <SecuritySection />}
        {active === "about" && <AboutSection platform={props.platform} apiHost={props.apiHost} />}
      </div>
    </div>
  );
}
