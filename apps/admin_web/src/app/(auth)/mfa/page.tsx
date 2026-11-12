"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getSupabaseClient } from "@/lib/supabase/client";

type Step =
  | { kind: "loading" }
  | { kind: "challenge"; factorId: string }
  | { kind: "enroll"; factorId: string; qr: string; secret: string }
  | { kind: "error"; message: string };

/** Second factor (TOTP) for administrators: verify an enrolled authenticator, or enrol one. */
export default function MfaPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>({ kind: "loading" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      const supabase = getSupabaseClient();
      if (!supabase) return setStep({ kind: "error", message: "Sign-in is not configured." });
      const { data: user } = await supabase.auth.getUser();
      if (!user.user) return router.replace("/login");
      const { data, error } = await supabase.auth.mfa.listFactors();
      if (error) return setStep({ kind: "error", message: "Could not load your security settings." });
      const verified = data.totp.find((f) => f.status === "verified");
      if (verified) return setStep({ kind: "challenge", factorId: verified.id });
      // Clean up half-finished enrolments, then start a new one.
      for (const f of data.all.filter((f) => f.status === "unverified")) {
        await supabase.auth.mfa.unenroll({ factorId: f.id });
      }
      const enrol = await supabase.auth.mfa.enroll({ factorType: "totp", friendlyName: "ZURUV Admin" });
      if (enrol.error || !enrol.data) return setStep({ kind: "error", message: "Could not start set-up." });
      setStep({
        kind: "enroll",
        factorId: enrol.data.id,
        qr: enrol.data.totp.qr_code,
        secret: enrol.data.totp.secret,
      });
    })();
  }, [router]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const supabase = getSupabaseClient();
    if (!supabase || (step.kind !== "challenge" && step.kind !== "enroll")) return;
    const code = String(new FormData(e.currentTarget).get("code") ?? "").trim();
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId: step.factorId, code });
    if (error) {
      setBusy(false);
      setError("That code did not work. Try the latest code from your authenticator app.");
      return;
    }
    router.replace("/dashboard");
    router.refresh();
  }

  if (step.kind === "loading") return <p className="text-sm text-muted-foreground">Loading...</p>;
  if (step.kind === "error") return <Alert>{step.message}</Alert>;

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div>
        <h1 className="text-xl font-semibold">
          {step.kind === "enroll" ? "Set up two-step verification" : "Two-step verification"}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {step.kind === "enroll"
            ? "Scan the QR code with an authenticator app, then enter the 6-digit code."
            : "Enter the 6-digit code from your authenticator app."}
        </p>
      </div>
      {step.kind === "enroll" && (
        <div className="space-y-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={step.qr} alt="QR code for your authenticator app" className="mx-auto size-40" />
          <p className="break-all text-center text-xs text-muted-foreground">
            Can&apos;t scan? Enter this key: <span className="font-mono">{step.secret}</span>
          </p>
        </div>
      )}
      {error && <Alert>{error}</Alert>}
      <div className="space-y-1.5">
        <Label htmlFor="code">Verification code</Label>
        <Input id="code" name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required />
      </div>
      <Button type="submit" className="w-full" disabled={busy}>
        {busy ? "Verifying..." : "Verify"}
      </Button>
    </form>
  );
}
