import { redirect } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { NoRole } from "@/components/data/no-role";
import { adminGet, safe } from "@/lib/admin-api";
import { getAdminAccess } from "@/lib/admin-access";

// Every request is authorised on the server; nothing here is cached or statically rendered.
export const dynamic = "force-dynamic";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  // The bell is a convenience: if the count cannot be read the console still works. It starts now
  // but is not awaited, so a slow count never delays the page; the bell streams in on its own.
  const unread = safe(adminGet<{ unread_count: number }>("/notifications/unread-count")).then((r) => (r.ok ? r.data.unread_count : 0), () => 0); // a dead session is handled by getAdminAccess below
  const access = await getAdminAccess();
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
      <Sidebar permissions={access.admin.permissions} />
      <div className="flex min-w-0 flex-1 flex-col overflow-x-clip bg-muted/40">
        <Header adminName={access.admin.full_name} unread={unread} permissions={access.admin.permissions} roleName={access.admin.admin_role} />
        <main className="min-w-0 flex-1 p-3 sm:p-4 md:p-6">
          {access.admin.admin_role ? children : <NoRole name={access.admin.full_name} />}
        </main>
      </div>
    </div>
  );
}
