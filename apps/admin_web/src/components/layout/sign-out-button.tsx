"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { getSupabaseClient } from "@/lib/supabase/client";

export function SignOutButton({ variant = "ghost" }: { variant?: "ghost" | "outline" }) {
  const router = useRouter();
  return (
    <Button
      variant={variant}
      size="sm"
      onClick={async () => {
        await getSupabaseClient()?.auth.signOut();
        router.replace("/login");
        router.refresh();
      }}
    >
      <LogOut className="size-4" aria-hidden />
      Sign out
    </Button>
  );
}
