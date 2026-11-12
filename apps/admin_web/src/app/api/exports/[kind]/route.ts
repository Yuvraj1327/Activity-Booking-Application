import { NextResponse, type NextRequest } from "next/server";
import { adminRequest, AdminApiError } from "@/lib/admin-api";

// Streams a CSV from the API using the signed-in admin's session. The browser never sees the API
// token; the API enforces admin-only access, audits the export and strips contact details.
const ALLOWED: Record<string, string[]> = {
  bookings: ["status", "payment_status", "venue_id", "from", "to"],
  payments: ["status", "from", "to"],
  customers: [],
  owners: [],
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
    const res = await adminRequest(`/admin/exports/${kind}.csv`, { query });
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
