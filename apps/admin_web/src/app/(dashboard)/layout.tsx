import { redirect } from "next/navigation";
import { Header } from "@/components/layout/header";
import { MobileNav, Sidebar } from "@/components/layout/sidebar";
import { adminGet, safe } from "@/lib/admin-api";
import { getAdminAccess } from "@/lib/admin-access";

// Every request is authorised on the server; nothing here is cached or statically rendered.
export const dynamic = "force-dynamic";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
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

  // The bell is a convenience: if the count cannot be read the console still works.
  const unread = await safe(adminGet<{ unread_count: number }>("/notifications/unread-count"));

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col bg-muted/40">
        <Header adminName={access.admin.full_name} unread={unread.ok ? unread.data.unread_count : 0} />
        <MobileNav />
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
