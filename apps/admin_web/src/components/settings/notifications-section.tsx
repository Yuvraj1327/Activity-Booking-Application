"use client";

import { useState } from "react";
import { savePreferences } from "@/app/(dashboard)/settings/actions";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import type { NotificationPreferences } from "@/lib/types";

const ROWS: { key: keyof NotificationPreferences; label: string; hint: string }[] = [
  { key: "email_enabled", label: "Email notifications", hint: "Receive important platform events (such as new owner registrations) by email." },
  { key: "push_enabled", label: "Push notifications", hint: "Receive push alerts on devices where you are signed in to the ZURUV app." },
];

export function NotificationsSection({ initial }: { initial: NotificationPreferences }) {
  const [prefs, setPrefs] = useState(initial);
  const [busy, setBusy] = useState<keyof NotificationPreferences | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function toggle(key: keyof NotificationPreferences, value: boolean) {
    const before = prefs;
    setPrefs({ ...prefs, [key]: value }); // optimistic
    setBusy(key);
    setMsg(null);
    const res = await savePreferences({ [key]: value });
    setBusy(null);
    if (res.ok && res.data) setPrefs(res.data);
    else setPrefs(before); // roll back
    setMsg({ ok: res.ok, text: res.message });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notifications</CardTitle>
        <CardDescription>Choose how ZURUV reaches you. In-app notifications in the bell are always on.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="divide-y divide-border">
          {ROWS.map(({ key, label, hint }) => (
            <li key={key} className="flex items-start justify-between gap-4 py-3 first:pt-0">
              <div>
                <p id={`pref-${key}`} className="text-sm font-medium">{label}</p>
                <p className="text-xs text-muted-foreground">{hint}</p>
              </div>
              <Switch aria-labelledby={`pref-${key}`} checked={prefs[key]} disabled={busy !== null} onCheckedChange={(v) => toggle(key, v)} />
            </li>
          ))}
        </ul>
        {msg && <Alert variant={msg.ok ? "info" : "error"}>{msg.text}</Alert>}
      </CardContent>
    </Card>
  );
}
