import type { Metadata } from "next";
import { ActionButton, REASON } from "@/components/data/action-button";
import { PageHeader } from "@/components/data/page-header";
import { ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";

export const metadata: Metadata = { title: "Platform switches" };
type S = { key: string; value: boolean; default: boolean; description: string };

const OPEN_QUESTION: Record<string, string> = {
  venue_approval_required: "Q4 — is venue publishing immediate, or does an admin approve?",
  refunds_enabled: "Q9 — cancellation and refund policy (windows, percentages, who can cancel).",
  payouts_enabled: "Q10 — how and when owners are paid; and the payout method / gateway product.",
  payout_requires_kyc: "N11 — what owner verification is required before payouts.",
};

export default async function PlatformPage() {
  const res = await safe(adminGet<{ items: S[] }>("/admin/settings"));
  if (!res.ok) return <ErrorState message={`Could not load the switches (${res.error.message}).`} />;
  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <PageHeader title="Platform switches" description="Decisions that belong to the business. Each switch starts on its SAFE value and changing it is recorded with your reason." />
      <Alert variant="info">Turn a switch on only after the matching decision has been made and written down. Several of them move real money or change what owners can do.</Alert>
      {res.data.items.map((s) => (
        <Card key={s.key} className="flex flex-wrap items-center justify-between gap-4 p-5" data-testid={`switch-${s.key}`}>
          <div className="min-w-0 flex-1">
            <p className="font-medium">{s.key.replace(/_/g, " ")} <Badge tone={s.value ? "success" : "neutral"}>{s.value ? "On" : "Off"}</Badge></p>
            <p className="mt-1 text-sm text-muted-foreground">{s.description}</p>
            <p className="mt-1 text-xs text-muted-foreground">Open question: {OPEN_QUESTION[s.key]}</p>
          </div>
          <ActionButton label={s.value ? "Turn off" : "Turn on"} title={`${s.value ? "Turn off" : "Turn on"} “${s.key.replace(/_/g, " ")}”?`} method="PUT" path={`/admin/settings/${s.key}`} fixed={{ value: !s.value }} fields={[REASON]} refresh={["/platform"]} danger={!s.value} variant={s.value ? "outline" : "default"} testId={`toggle-${s.key}`}
            description={!s.value && s.key === "refunds_enabled" ? "Admins with the refund permission will be able to send real refunds through Razorpay." : !s.value && s.key === "payouts_enabled" ? "Payout records can be created, approved and marked paid." : undefined} />
        </Card>
      ))}
    </div>
  );
}
