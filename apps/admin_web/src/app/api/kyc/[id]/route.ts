import { NextResponse, type NextRequest } from "next/server";
import { adminRequest, AdminApiError } from "@/lib/admin-api";

// Streams one KYC document from the API using the signed-in admin's session. The browser never sees the
// storage location or any token; the API checks the `kyc.review` permission and records every view.
export const dynamic = "force-dynamic";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!UUID.test(id)) return NextResponse.json({ code: "NOT_FOUND" }, { status: 404 });
  try {
    const res = await adminRequest(`/admin/kyc/documents/${id}/file`);
    return new NextResponse(res.body, {
      status: 200,
      headers: {
        "Content-Type": res.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition": res.headers.get("content-disposition") ?? "inline",
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
      },
    });
  } catch (e) {
    if (e instanceof AdminApiError) return NextResponse.json({ code: e.code, message: e.message }, { status: e.status || 502 });
    throw e;
  }
}
