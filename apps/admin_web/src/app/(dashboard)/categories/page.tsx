import type { Metadata } from "next";
import { ActionButton } from "@/components/data/action-button";
import { PageHeader } from "@/components/data/page-header";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatNumber } from "@/lib/format";

export const metadata: Metadata = { title: "Sports" };
type C = { id: string; slug: string; name: string; icon_key: string | null; sort_order: number; is_active: boolean; venues: number; bookings: number };

export default async function CategoriesPage() {
  const res = await safe(adminGet<{ items: C[] }>("/admin/categories"));
  const back = ["/categories"];
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Sports categories" description="The sports shown in both apps. Categories are never deleted, so venues and bookings keep their links: deactivate to hide one."
        actions={<ActionButton label="Add sport" title="Add a sport" path="/admin/categories" variant="default" refresh={back} testId="category-add"
          fields={[{ name: "name", label: "Name", required: true, maxLength: 80 }, { name: "slug", label: "Slug (optional)", help: "Lower-case letters, digits and dashes. Created from the name if empty.", maxLength: 80 },
            { name: "icon_key", label: "Icon key (optional)", maxLength: 60 }, { name: "sort_order", label: "Sort order", type: "number", defaultValue: 0, min: 0, max: 10000 }]} />} />
      <Card>
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load sports (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No sports yet" /> : (
          <Table>
            <THead><TR><TH>Sport</TH><TH>Slug</TH><TH className="text-right">Order</TH><TH className="text-right">Venues</TH><TH className="text-right">Bookings</TH><TH>Status</TH><TH>Actions</TH></TR></THead>
            <TBody>{res.data.items.map((c) => (
              <TR key={c.id}>
                <TD className="font-medium">{c.name}</TD><TD className="font-mono text-xs">{c.slug}</TD><TD className="text-right tabular-nums">{c.sort_order}</TD>
                <TD className="text-right tabular-nums">{formatNumber(c.venues)}</TD><TD className="text-right tabular-nums">{formatNumber(c.bookings)}</TD>
                <TD><Badge tone={c.is_active ? "success" : "neutral"}>{c.is_active ? "Active" : "Inactive"}</Badge></TD>
                <TD><div className="flex gap-2">
                  <ActionButton label="Edit" title={`Edit ${c.name}`} method="PATCH" path={`/admin/categories/${c.id}`} refresh={back}
                    fields={[{ name: "name", label: "Name", required: true, defaultValue: c.name, maxLength: 80 }, { name: "icon_key", label: "Icon key", defaultValue: c.icon_key, maxLength: 60 }, { name: "sort_order", label: "Sort order", type: "number", defaultValue: c.sort_order, min: 0, max: 10000 }]} />
                  <ActionButton label={c.is_active ? "Deactivate" : "Activate"} title={`${c.is_active ? "Deactivate" : "Activate"} ${c.name}?`} method="PATCH" path={`/admin/categories/${c.id}`} fixed={{ is_active: !c.is_active }} refresh={back} danger={c.is_active}
                    description={c.is_active ? `It disappears from the apps' sport lists. ${c.venues} venue(s) keep their link, and existing bookings are unaffected.` : "It appears in the apps again."} />
                </div></TD>
              </TR>
            ))}</TBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
