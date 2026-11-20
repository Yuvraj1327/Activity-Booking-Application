"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { getSupabaseClient } from "@/lib/supabase/client";

/** Sign out of this device only, or of every device (revokes all refresh tokens). */
export function SessionActions() {
  const router = useRouter();
  const [busy, setBusy] = useState<"local" | "global" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(scope: "local" | "global") {
    const supabase = getSupabaseClient();
    if (!supabase) return setError("Sign-in is not configured.");
    if (scope === "global" && !window.confirm("Sign out of ALL devices, including this one? You will need to sign in again everywhere.")) return;
    setBusy(scope);
    setError(null);
    const { error } = await supabase.auth.signOut({ scope });
    if (error) {
      setBusy(null);
      return setError("Could not sign out. Please try again.");
    }
    router.replace("/login");
    router.refresh();
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" disabled={busy !== null} onClick={() => run("local")}>
          <LogOut className="size-4" aria-hidden />
          {busy === "local" ? "Signing out..." : "Sign out of this device"}
        </Button>
        <Button variant="outline" size="sm" disabled={busy !== null} onClick={() => run("global")}>
          {busy === "global" ? "Signing out..." : "Sign out of all devices"}
        </Button>
      </div>
      {error && <Alert>{error}</Alert>}
    </div>
  );
}
