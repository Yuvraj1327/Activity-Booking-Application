"use client";

import { useEffect, useState, type FormEvent } from "react";
import { SessionActions } from "@/components/settings/session-actions";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getSupabaseClient } from "@/lib/supabase/client";
import type { MyProfile } from "@/lib/types";

const fmt = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "Unknown";

function friendly(code: string | undefined, fallback: string): string {
  switch (code) {
    case "same_password": return "Your new password must be different from the current one.";
    case "weak_password": return "That password is too weak. Use a longer, less common password.";
    case "over_request_rate_limit":
    case "over_email_send_rate_limit": return "Too many attempts. Please wait a moment and try again.";
    case "reauth_nonce_missing":
    case "reauthentication_not_valid": return "That verification code is not valid. Check the latest email and try again.";
    default: return fallback;
  }
}

function PasswordForm() {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [nonce, setNonce] = useState("");
  const [needsCode, setNeedsCode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({});

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (password.length < 8) next.password = "Use at least 8 characters.";
    if (confirm !== password) next.confirm = "Passwords do not match.";
    setErrors(next);
    if (Object.keys(next).length) return;
    const supabase = getSupabaseClient();
    if (!supabase) return setMsg({ ok: false, text: "Sign-in is not configured." });

    setBusy(true);
    setMsg(null);
    // Changed through Supabase Auth with the current verified session; no password is stored by us.
    const { error } = await supabase.auth.updateUser({ password, ...(needsCode ? { nonce: nonce.trim() } : {}) });
    if (error && error.code === "reauthentication_needed") {
      // Supabase wants proof of email ownership first: it mails a one-time code.
      const re = await supabase.auth.reauthenticate();
      setBusy(false);
      if (re.error) return setMsg({ ok: false, text: friendly(re.error.code, "Could not send a verification code. Please try again.") });
      setNeedsCode(true);
      return setMsg({ ok: true, text: "We emailed you a verification code. Enter it below to confirm the change." });
    }
    setBusy(false);
    if (error) return setMsg({ ok: false, text: friendly(error.code, "Could not change your password. Please try again.") });
    setPassword("");
    setConfirm("");
    setNonce("");
    setNeedsCode(false);
    setMsg({ ok: true, text: "Password changed. Other devices stay signed in until their session ends; use “Sign out of all devices” if you are worried." });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="new-password">New password</Label>
        <Input id="new-password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} aria-invalid={!!errors.password} />
        {errors.password && <p className="text-xs text-destructive">{errors.password}</p>}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="confirm-password">Confirm new password</Label>
        <Input id="confirm-password" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-invalid={!!errors.confirm} />
        {errors.confirm && <p className="text-xs text-destructive">{errors.confirm}</p>}
      </div>
      {needsCode && (
        <div className="space-y-1.5">
          <Label htmlFor="nonce">Verification code from your email</Label>
          <Input id="nonce" inputMode="numeric" autoComplete="one-time-code" value={nonce} onChange={(e) => setNonce(e.target.value)} />
        </div>
      )}
      {msg && <Alert variant={msg.ok ? "info" : "error"}>{msg.text}</Alert>}
      <Button type="submit" disabled={busy || (needsCode && !nonce.trim())}>
        {busy ? "Working..." : needsCode ? "Confirm password change" : "Change password"}
      </Button>
    </form>
  );
}

export function AccountSection({ email, profile }: { email: string | null; profile: MyProfile | null }) {
  const [lastSignIn, setLastSignIn] = useState<string | null>(null);
  useEffect(() => {
    getSupabaseClient()?.auth.getUser().then(({ data }) => setLastSignIn(data.user?.last_sign_in_at ?? null));
  }, []);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Information about your administrator account.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="divide-y divide-border">
            {[
              ["Email", email ?? "Unknown"],
              ["Role", profile ? profile.role.charAt(0).toUpperCase() + profile.role.slice(1) : "Administrator"],
              ["Status", profile ? (profile.status === "active" ? "Active" : "Suspended") : "Unknown"],
              ["Member since", fmt(profile?.created_at)],
              ["Last sign-in", fmt(lastSignIn)],
            ].map(([k, v]) => (
              <div key={k} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
                <dt className="text-sm text-muted-foreground">{k}</dt>
                <dd className="break-all text-sm font-medium">{v}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>Choose a strong password you do not use anywhere else.</CardDescription>
        </CardHeader>
        <CardContent>
          <PasswordForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sessions</CardTitle>
          <CardDescription>Signing out of all devices ends every active session for your account.</CardDescription>
        </CardHeader>
        <CardContent>
          <SessionActions />
        </CardContent>
      </Card>
    </div>
  );
}
