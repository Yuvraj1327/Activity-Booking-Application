"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { getSupabaseClient } from "@/lib/supabase/client";

const CONFIRM_WINDOW_MS = 4000;

/** Two-step sign out: the first click asks "Confirm sign out?", the second one signs out. */
export function SignOutButton({ variant = "ghost" }: { variant?: "ghost" | "outline" }) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  // An unconfirmed click quietly expires, so a stray click never leaves the button armed.
  useEffect(() => {
    if (!confirming) return;
    const t = setTimeout(() => setConfirming(false), CONFIRM_WINDOW_MS);
    return () => clearTimeout(t);
  }, [confirming]);

  async function signOut() {
    setBusy(true);
    await getSupabaseClient()?.auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <Button
      variant={confirming ? "default" : variant}
      size="sm"
      disabled={busy}
      onClick={() => (confirming ? signOut() : setConfirming(true))}
      onBlur={() => setConfirming(false)}
      onKeyDown={(e) => e.key === "Escape" && setConfirming(false)}
      aria-live="polite"
    >
      <LogOut className="size-4" aria-hidden />
      {busy ? "Signing out..." : confirming ? "Confirm sign out?" : "Sign out"}
    </Button>
  );
}
