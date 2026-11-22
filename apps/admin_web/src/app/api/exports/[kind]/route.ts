import { NextResponse, type NextRequest } from "next/server";
import { adminRequest, AdminApiError } from "@/lib/admin-api";

// Streams a CSV from the API using the signed-in admin's session. The browser never sees the API
// token; the API enforces admin-only access, audits the export and strips contact details.
const ALLOWED: Record<string, string[]> = {
  bookings: ["status", "payment_status", "venue_id", "owner_id", "category_id", "city_id", "refund_status", "from", "to"],
  payments: ["status", "from", "to"],
  customers: [],
  owners: [],
  refunds: ["status", "from", "to"],
  ledger: ["owner_id", "from", "to"],
  payouts: ["owner_id"],
  analytics: ["dimension", "from", "to"],
  reconciliation: ["run_id"],
};

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest, { params }: { params: Promise<{ kind: string }> }) {
  const { kind } = await params;
  const allowed = ALLOWED[kind];
  if (!allowed) return NextResponse.json({ code: "NOT_FOUND" }, { status: 404 });
  const query: Record<string, string> = {};
  for (const k of allowed) {
    const v = request.nextUrl.searchParams.get(k);
    if (v) query[k] = v;
  }
  try {
    const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (kind === "reconciliation" && !UUID.test(query.run_id ?? "")) return NextResponse.json({ code: "NOT_FOUND" }, { status: 404 });
    const path = kind === "reconciliation" ? `/admin/exports/reconciliation/${query.run_id}.csv` : `/admin/exports/${kind}.csv`;
    const res = await adminRequest(path, { query: kind === "reconciliation" ? {} : query });
    return new NextResponse(res.body, {
      status: 200,
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="zuruv-${kind}.csv"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (e) {
    if (e instanceof AdminApiError) return NextResponse.json({ code: e.code, message: e.message }, { status: e.status || 502 });
    throw e;
  }
}
