import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/data/page-header";
import { Pagination } from "@/components/data/pagination";
import { StatusBadge } from "@/components/data/status-badge";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { formatDateTime } from "@/lib/format";
import { PAGE_SIZE, pageOf, type SearchParams } from "@/lib/query";
import type { Cursor } from "@/lib/types";

export const metadata: Metadata = { title: "Owner KYC" };

type Item = { owner_id: string; owner_name: string; business_name: string; kyc_status: string; pending_documents: number; waiting_since: string };

export default async function KycQueuePage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const { offset, page } = pageOf(params);
  const res = await safe(adminGet<Cursor<Item> & { items: Item[] }>("/admin/kyc/queue", { limit: PAGE_SIZE, offset }));
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Owner KYC" description="Owners with documents waiting for review, oldest first. Documents are private: every view is recorded in the audit log." />
      <Card>
        {!res.ok ? <div className="p-4"><ErrorState message={`Could not load the queue (${res.error.message}).`} /></div> : res.data.items.length === 0 ? (
          <EmptyState title="Nothing to review" description="New submissions appear here." />
        ) : (
          <>
            <Table>
              <THead><TR><TH>Owner</TH><TH>Business</TH><TH>Status</TH><TH className="text-right">Documents waiting</TH><TH>Waiting since</TH></TR></THead>
              <TBody>{res.data.items.map((i) => (
                <TR key={i.owner_id}>
                  <TD><Link href={`/owners/${i.owner_id}#kyc`} className="font-medium text-primary hover:underline">{i.owner_name}</Link></TD>
                  <TD>{i.business_name}</TD><TD><StatusBadge status={i.kyc_status} /></TD>
                  <TD className="text-right tabular-nums">{i.pending_documents}</TD><TD className="whitespace-nowrap text-xs">{formatDateTime(i.waiting_since)}</TD>
                </TR>
              ))}</TBody>
            </Table>
            <Pagination path="/kyc" params={params} page={page} hasMore={res.data.has_more} shown={res.data.items.length} />
          </>
        )}
      </Card>
    </div>
  );
}
