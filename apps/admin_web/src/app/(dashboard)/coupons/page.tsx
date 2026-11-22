import type { Metadata } from "next";
import Link from "next/link";
import { ActionButton, type Field } from "@/components/data/action-button";
import { FilterBar } from "@/components/data/filter-bar";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime, formatMoney } from "@/lib/format";
import { describe, type Coupon } from "@/lib/coupon";
import { one, PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Coupons" };

export default async function CouponsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const active = one(params, "active");
  const res = await safe(adminGet<Cursor<Coupon> & { items: Coupon[] }>("/admin/coupons", { q: one(params, "q"), active: active === "1" ? "true" : active === "0" ? "false" : undefined, limit: PAGE_SIZE, offset }));
  const create: Field[] = [
    { name: "code", label: "Code", required: true, maxLength: 30, placeholder: "WELCOME10", help: "3–30 letters, digits, - or _. Customers type it at checkout." },
    { name: "description", label: "Description", maxLength: 300 },
    { name: "discount_type", label: "Discount type", type: "select", required: true, defaultValue: "percent", options: [{ value: "percent", label: "Percentage" }, { value: "fixed", label: "Fixed amount" }] },
    { name: "percent_bps", label: "Percentage (basis points)", type: "number", min: 1, max: 10000, help: "For a percentage coupon: 1000 = 10%. Leave empty for a fixed coupon." },
    { name: "fixed_paise", label: "Fixed amount (₹)", type: "money", help: "For a fixed coupon. Leave empty for a percentage coupon." },
    { name: "max_discount_paise", label: "Maximum discount (₹)", type: "money" },
    { name: "min_booking_paise", label: "Minimum booking amount (₹)", type: "money" },
    { name: "valid_from", label: "Valid from", type: "datetime" }, { name: "valid_until", label: "Valid until", type: "datetime" },
    { name: "usage_limit_total", label: "Total redemptions allowed", type: "number", min: 1 }, { name: "usage_limit_per_user", label: "Per customer", type: "number", min: 1 },
    { name: "first_booking_only", label: "First booking only", type: "checkbox" },
    { name: "eligible_category_ids", label: "Only for these sport IDs", type: "list", help: "Comma-separated IDs. Empty = all sports." },
    { name: "eligible_city_ids", label: "Only for these city IDs", type: "list" }, { name: "eligible_venue_ids", label: "Only for these venue IDs", type: "list" },
  ];
  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader title="Coupons and offers" description="Discounts are validated and calculated by the server at quote and booking time. A discount can never take a booking below the ₹1 payment minimum."
        actions={<ActionButton label="New coupon" title="Create a coupon" path="/admin/coupons" variant="default" refresh={["/coupons"]} fields={create} testId="coupon-new" />} />
      <Card>
        <FilterBar path="/coupons" params={params} fields={[{ kind: "search", name: "q", placeholder: "Code" }, { kind: "select", name: "active", label: "State", options: [{ value: "1", label: "Active" }, { value: "0", label: "Inactive" }] }]} />
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load coupons (${res.error.message}).`} /></div> : res.data.items.length === 0 ? <EmptyState title="No coupons" /> : (
          <>
            <Table>
              <THead><TR><TH>Code</TH><TH>Discount</TH><TH>Min booking</TH><TH>Valid</TH><TH className="text-right">Used</TH><TH>Rules</TH><TH>State</TH><TH>Actions</TH></TR></THead>
              <TBody>{res.data.items.map((c) => (
                <TR key={c.id}>
                  <TD><Link href={`/coupons/${c.id}`} className="font-mono font-medium text-primary hover:underline">{c.code}</Link>{c.description && <p className="text-xs text-muted-foreground">{c.description}</p>}</TD>
                  <TD>{describe(c)}</TD><TD>{c.min_booking_paise ? formatMoney(c.min_booking_paise) : "—"}</TD>
                  <TD className="whitespace-nowrap text-xs">{c.valid_from ? formatDateTime(c.valid_from) : "any time"} → {c.valid_until ? formatDateTime(c.valid_until) : "no end"}</TD>
                  <TD className="text-right tabular-nums">{c.redeemed ?? 0}{c.usage_limit_total ? ` / ${c.usage_limit_total}` : ""}</TD>
                  <TD className="text-xs text-muted-foreground">{[c.first_booking_only && "first booking", c.usage_limit_per_user && `${c.usage_limit_per_user}/customer`, c.eligible_category_ids.length && "sports", c.eligible_city_ids.length && "cities", c.eligible_venue_ids.length && "venues"].filter(Boolean).join(", ") || "—"}</TD>
                  <TD><Badge tone={c.is_active ? "success" : "neutral"}>{c.is_active ? "Active" : "Inactive"}</Badge></TD>
                  <TD><ActionButton label={c.is_active ? "Deactivate" : "Activate"} method="PATCH" path={`/admin/coupons/${c.id}`} fixed={{ is_active: !c.is_active }} refresh={["/coupons", `/coupons/${c.id}`]} danger={c.is_active} title={`${c.is_active ? "Deactivate" : "Activate"} ${c.code}?`} /></TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/coupons" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
