import type { Metadata } from "next";
import { ActionButton, REASON, type Field } from "@/components/data/action-button";
import { PageHeader } from "@/components/data/page-header";
import { StatusBadge } from "@/components/data/status-badge";
import { ErrorState } from "@/components/data/states";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { adminGet, safe } from "@/lib/admin-api";
import { getAdminAccess } from "@/lib/admin-access";
import { formatDateTime } from "@/lib/format";

export const metadata: Metadata = { title: "Admin roles" };

type Perm = { key: string; label: string; sensitive: boolean; module: string };
type Role = { id: string; name: string; description: string | null; permissions: string[]; is_system: boolean; members: number; updated_at: string };
type Admin = { id: string; full_name: string; email: string | null; status: string; role_id: string | null; role_name: string | null; assigned_at: string | null };

export default async function RolesPage() {
  const access = await getAdminAccess();
  const me = access.kind === "ok" ? access.admin : null;
  const [roles, perms, admins] = await Promise.all([
    safe(adminGet<{ items: Role[] }>("/admin/roles")), safe(adminGet<{ items: Perm[] }>("/admin/permissions")), safe(adminGet<{ items: Admin[] }>("/admin/admins")),
  ]);
  if (!roles.ok || !perms.ok || !admins.ok) {
    const e = !roles.ok ? roles.error : !perms.ok ? perms.error : (admins as { error: { message: string } }).error;
    return <ErrorState message={`Could not load roles (${e.message}).`} />;
  }
  const mine = new Set(me?.permissions ?? []);
  const grantable = perms.data.items.filter((p) => mine.has(p.key));
  const permField = (def = ""): Field => ({
    name: "permissions", label: "Permissions", type: "checks", defaultValue: def,
    options: grantable.map((p) => ({ value: p.key, label: `${p.label}${p.sensitive ? " (sensitive)" : ""}` })),
    help: "You can only grant permissions you hold yourself.",
  });
  const roleOptions = roles.data.items.map((r) => ({ value: r.id, label: r.name }));
  const back = ["/roles"];
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader title="Admin roles and permissions" description="What each administrator may see and do. The server checks the permission on every request; hidden buttons are only a convenience."
        actions={<ActionButton label="New role" title="Create a role" path="/admin/roles" variant="default" refresh={back} testId="role-new"
          fields={[{ name: "name", label: "Role name", required: true, maxLength: 60 }, { name: "description", label: "Description", maxLength: 300 }, permField()]} />} />
      <Alert variant="info">A new administrator has <strong>no</strong> permissions until a role is assigned here. You cannot change your own role, nor grant a permission you do not hold. The built-in <code>super_admin</code> role always holds every permission and can only be assigned by another super_admin.</Alert>
      <Card data-testid="roles-table">
        <CardHeader><CardTitle>Roles</CardTitle></CardHeader>
        <Table>
          <THead><TR><TH>Role</TH><TH>Permissions</TH><TH className="text-right">Administrators</TH><TH>Actions</TH></TR></THead>
          <TBody>{roles.data.items.map((r) => (
            <TR key={r.id}>
              <TD><p className="font-medium">{r.name}{r.is_system && <Badge tone="primary" className="ml-2">Built-in</Badge>}</p><p className="text-xs text-muted-foreground">{r.description}</p></TD>
              <TD><div className="flex max-w-xl flex-wrap gap-1">{r.is_system ? <Badge tone="primary">All {r.permissions.length} permissions</Badge> : r.permissions.length === 0 ? <span className="text-xs text-muted-foreground">None</span> : r.permissions.map((p) => <Badge key={p} tone={perms.data.items.find((x) => x.key === p)?.sensitive ? "warning" : "neutral"}>{p}</Badge>)}</div></TD>
              <TD className="text-right tabular-nums">{r.members}</TD>
              <TD>{!r.is_system && (
                <div className="flex gap-2">
                  <ActionButton label="Edit permissions" title={`Edit ${r.name}`} method="PATCH" path={`/admin/roles/${r.id}`} refresh={back} fields={[{ name: "description", label: "Description", defaultValue: r.description, maxLength: 300 }, permField(r.permissions.join(",")), REASON]} />
                  <ActionButton label="Delete" title={`Delete ${r.name}?`} method="DELETE" path={`/admin/roles/${r.id}`} refresh={back} danger fields={[REASON]} description="Only a role nobody holds can be deleted." />
                </div>
              )}</TD>
            </TR>
          ))}</TBody>
        </Table>
      </Card>
      <Card data-testid="admins-table">
        <CardHeader><CardTitle>Administrators</CardTitle></CardHeader>
        <Table>
          <THead><TR><TH>Administrator</TH><TH>Account</TH><TH>Role</TH><TH>Since</TH><TH>Action</TH></TR></THead>
          <TBody>{admins.data.items.map((a) => (
            <TR key={a.id}>
              <TD><p className="font-medium">{a.full_name}{a.id === me?.id && " (you)"}</p><p className="text-xs text-muted-foreground">{a.email}</p></TD>
              <TD><StatusBadge status={a.status} /></TD>
              <TD>{a.role_name ?? <span className="text-warning-foreground">No role: no access</span>}</TD>
              <TD className="text-xs">{formatDateTime(a.assigned_at)}</TD>
              <TD>{a.id !== me?.id && (
                <ActionButton label={a.role_name ? "Change role" : "Assign role"} title={`Role for ${a.full_name}`} method="PUT" path={`/admin/admins/${a.id}/role`} refresh={back}
                  fields={[{ name: "role_id", label: "Role", type: "select", defaultValue: a.role_id, options: roleOptions, emptyAsNull: true, help: "Choose “—” to remove all access." }, REASON]} />
              )}</TD>
            </TR>
          ))}</TBody>
        </Table>
        <p className="px-6 py-3 text-xs text-muted-foreground">New administrators are created by an operator with <code>python -m scripts.create_admin</code>; there is no way to create one from the web.</p>
      </Card>
    </div>
  );
}
