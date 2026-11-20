import { redirect } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { adminGet, safe } from "@/lib/admin-api";
import { getAdminAccess } from "@/lib/admin-access";

// Every request is authorised on the server; nothing here is cached or statically rendered.
export const dynamic = "force-dynamic";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  // Independent calls run together; both reuse the single verified session of this request.
  const [access, unread] = await Promise.all([
    getAdminAccess(),
    // The bell is a convenience: if the count cannot be read the console still works.
    safe(adminGet<{ unread_count: number }>("/notifications/unread-count")),
  ]);
  switch (access.kind) {
    case "ok":
      break;
    case "not_configured":
    case "signed_out":
      redirect("/login");
    case "mfa_required":
      redirect("/mfa");
    case "forbidden":
      redirect("/unauthorized");
    case "error":
      throw new Error(access.message);
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-x-clip bg-muted/40">
        <Header adminName={access.admin.full_name} unread={unread.ok ? unread.data.unread_count : 0} />
        <main className="min-w-0 flex-1 p-3 sm:p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
