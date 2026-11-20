"use client";

import { ShieldAlert, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { SessionActions } from "@/components/settings/session-actions";
import { Alert } from "@/components/ui/alert";
import { buttonLink } from "@/components/ui/button-link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getSupabaseClient } from "@/lib/supabase/client";

type Mfa = { enabled: boolean; factorName: string | null; addedAt: string | null; sessionVerified: boolean };

export function SecuritySection() {
  const [mfa, setMfa] = useState<Mfa | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const supabase = getSupabaseClient();
      if (!supabase) return setError("Sign-in is not configured.");
      const [factors, aal] = await Promise.all([supabase.auth.mfa.listFactors(), supabase.auth.mfa.getAuthenticatorAssuranceLevel()]);
      if (factors.error) return setError("Could not load your two-factor authentication status.");
      const verified = factors.data.totp.find((f) => f.status === "verified");
      setMfa({
        enabled: !!verified,
        factorName: verified?.friendly_name ?? null,
        addedAt: verified?.created_at ?? null,
        sessionVerified: aal.data?.currentLevel === "aal2",
      });
    })();
  }, []);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Two-factor authentication</CardTitle>
          <CardDescription>An authenticator app code is required in addition to your password.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <Alert>{error}</Alert>}
          {!mfa && !error && <p className="text-sm text-muted-foreground">Loading...</p>}
          {mfa && (
            <>
              <div className="flex items-start gap-3">
                {mfa.enabled ? <ShieldCheck className="mt-0.5 size-5 text-success" aria-hidden /> : <ShieldAlert className="mt-0.5 size-5 text-warning" aria-hidden />}
                <div>
                  <p className="text-sm font-medium" data-testid="mfa-status">{mfa.enabled ? "Enabled" : "Not enabled"}</p>
                  <p className="text-xs text-muted-foreground">
                    {mfa.enabled
                      ? `${mfa.factorName ?? "Authenticator app"}${mfa.addedAt ? `, added ${new Date(mfa.addedAt).toLocaleDateString()}` : ""}. ${
                          mfa.sessionVerified ? "This session is verified with your second factor." : "This session has not been verified with your second factor yet."
                        }`
                      : "Your account is protected by your password only. Set up an authenticator app to add a second step."}
                  </p>
                </div>
              </div>
              {(!mfa.enabled || !mfa.sessionVerified) && (
                <Link href="/mfa" className={buttonLink}>
                  {mfa.enabled ? "Verify this session" : "Set up two-factor authentication"}
                </Link>
              )}
              {mfa.enabled && <p className="text-xs text-muted-foreground">Removing a second factor is not available here to prevent accidental lock-out. Contact another administrator if your device is lost.</p>}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sessions</CardTitle>
          <CardDescription>Sign out here, or revoke access on every device if you suspect misuse.</CardDescription>
        </CardHeader>
        <CardContent>
          <SessionActions />
        </CardContent>
      </Card>
    </div>
  );
}
