import type { Metadata } from "next";
import Link from "next/link";
import { ActionButton } from "@/components/data/action-button";
import { FilterBar } from "@/components/data/filter-bar";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, titleCase } from "@/lib/format";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Content" };
type C = { id: string; kind: string; slug: string; audience: string; title: string; status: string; sort_order: number; published_at: string | null; updated_at: string };

const KNOWN = [
  ["terms-customer", "Terms & Conditions for players (Settings → About in the customer app)"],
  ["terms-owner", "Terms & Conditions for venue owners (Settings → About in the owner app)"],
  ["privacy", "Privacy Policy (both apps)"],
];

export default async function CmsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const res = await safe(adminGet<Cursor<C> & { items: C[] }>("/admin/cms", { kind: one(params, "kind"), status: one(params, "status"), q: one(params, "q"), limit: PAGE_SIZE, offset }));
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHeader title="Content (CMS)" description="Legal pages and help FAQs that both apps display. Drafts are never shown; publishing takes effect within a minute."
        actions={<ActionButton label="New content" title="Create content" path="/admin/cms" variant="default" refresh={["/cms"]} testId="cms-new"
          fields={[{ name: "kind", label: "Type", type: "select", required: true, defaultValue: "page", options: [{ value: "page", label: "Page (terms, privacy…)" }, { value: "faq", label: "FAQ (question + answer)" }] },
            { name: "slug", label: "Slug", required: true, maxLength: 80, help: "Lower-case letters, digits, dashes. The apps look pages up by slug (see below). Cannot change later." },
            { name: "audience", label: "Shown to", type: "select", required: true, defaultValue: "all", options: [{ value: "all", label: "Everyone" }, { value: "customer", label: "Players" }, { value: "owner", label: "Venue owners" }] },
            { name: "title", label: "Title / question", required: true, maxLength: 200 }, { name: "body", label: "Body / answer", type: "textarea", required: true, maxLength: 50000 },
            { name: "sort_order", label: "Order", type: "number", defaultValue: 0, min: 0 }]} />} />
      <Card className="p-4 text-sm"><p className="font-medium">Pages the apps already look for</p><ul className="mt-1 list-disc pl-5 text-muted-foreground">{KNOWN.map(([s, d]) => <li key={s}><code className="text-foreground">{s}</code> — {d}</li>)}<li>Any published <strong>FAQ</strong> is added to the Help screen (until some exist, the built-in FAQs are shown).</li></ul></Card>
      <Card>
        <FilterBar path="/cms" params={params} fields={[{ kind: "search", name: "q", placeholder: "Title or slug" }, { kind: "select", name: "kind", label: "Type", options: ["page", "faq"] }, { kind: "select", name: "status", label: "Status", options: ["draft", "published"] }]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load content (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No content yet" description="Create the Terms and Privacy pages with the slugs above." /> : (
          <>
            <Table>
              <THead><TR><TH>Title</TH><TH>Slug</TH><TH>Type</TH><TH>Shown to</TH><TH>Status</TH><TH>Published</TH><TH>Updated</TH><TH>Actions</TH></TR></THead>
              <TBody>{res.data.items.map((c) => (
                <TR key={c.id}>
                  <TD><Link href={`/cms/${c.id}`} className="font-medium text-primary hover:underline">{c.title}</Link></TD><TD className="font-mono text-xs">{c.slug}</TD><TD>{titleCase(c.kind)}</TD><TD>{titleCase(c.audience)}</TD>
                  <TD><StatusBadge status={c.status === "published" ? "published" : "draft"} /></TD><TD className="text-xs">{formatDateTime(c.published_at)}</TD><TD className="text-xs">{formatDateTime(c.updated_at)}</TD>
                  <TD><ActionButton label={c.status === "published" ? "Unpublish" : "Publish"} path={`/admin/cms/${c.id}/${c.status === "published" ? "unpublish" : "publish"}`} refresh={["/cms", `/cms/${c.id}`]} danger={c.status === "published"} title={`${c.status === "published" ? "Unpublish" : "Publish"} “${c.title}”?`} description={c.status === "published" ? "The apps stop showing it." : "The apps start showing it."} /></TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/cms" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
