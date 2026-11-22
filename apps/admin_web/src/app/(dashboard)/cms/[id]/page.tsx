import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ActionButton } from "@/components/data/action-button";
import { Detail, DetailGrid } from "@/components/data/detail";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { ErrorState } from "@/components/data/states";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, titleCase } from "@/lib/format";

export const metadata: Metadata = { title: "Content entry" };
type C = { id: string; kind: string; slug: string; audience: string; title: string; body: string; status: string; sort_order: number; published_at: string | null; created_at: string; updated_at: string };

export default async function CmsEntryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(adminGet<C>(`/admin/cms/${encodeURIComponent(id)}`));
  if (!res.ok) {
    if (res.error.status === 404 || res.error.status === 422) notFound();
    return <ErrorState message={`Could not load this entry (${res.error.message}).`} />;
  }
  const c = res.data;
  const published = c.status === "published";
  const back = [`/cms/${c.id}`, "/cms"];
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader title={c.title} description={`${titleCase(c.kind)} · ${c.slug}`} actions={<>
        <StatusBadge status={published ? "published" : "draft"} />
        <ActionButton label="Edit" title={`Edit ${c.slug}`} method="PATCH" path={`/admin/cms/${c.id}`} refresh={back} testId="cms-edit"
          description={published ? "This entry is live: saving changes what the apps show." : undefined}
          fields={[{ name: "title", label: "Title / question", required: true, defaultValue: c.title, maxLength: 200 }, { name: "body", label: "Body / answer", type: "textarea", required: true, defaultValue: c.body, maxLength: 50000 },
            { name: "audience", label: "Shown to", type: "select", required: true, defaultValue: c.audience, options: [{ value: "all", label: "Everyone" }, { value: "customer", label: "Players" }, { value: "owner", label: "Venue owners" }] },
            { name: "sort_order", label: "Order", type: "number", defaultValue: c.sort_order, min: 0 }]} />
        <ActionButton label={published ? "Unpublish" : "Publish"} path={`/admin/cms/${c.id}/${published ? "unpublish" : "publish"}`} variant="default" danger={published} refresh={back} title={published ? "Unpublish this entry?" : "Publish this entry?"} />
      </>} />
      <Card><CardHeader><CardTitle>Details</CardTitle></CardHeader><DetailGrid>
        <Detail label="Shown to">{titleCase(c.audience)}</Detail><Detail label="Published">{formatDateTime(c.published_at)}</Detail><Detail label="Last updated">{formatDateTime(c.updated_at)}</Detail>
      </DetailGrid></Card>
      <Card><CardHeader><CardTitle>Preview</CardTitle></CardHeader><div className="whitespace-pre-wrap px-6 pb-6 text-sm leading-relaxed" data-testid="cms-body">{c.body}</div></Card>
    </div>
  );
}
