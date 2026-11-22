"""Admin builders shared by the admin-operations tests."""

import uuid

from tests.conftest import auth_headers, seed_profile, sql


def admin_with(db: str, perms: list[str] | None = None, *, name: str = "Ada Admin") -> dict:
    """`perms=None` -> super_admin; a list -> a fresh custom role with exactly those permissions."""
    if perms is None:
        uid = seed_profile(db, "admin", name=name)
    else:
        uid = seed_profile(db, "admin", name=name, grant=None)
        role = sql(
            db,
            "INSERT INTO public.admin_roles (name, permissions) VALUES ($1, $2) RETURNING id",
            f"role-{uuid.uuid4().hex[:8]}", perms,
        )[0]["id"]  # fmt: skip
        sql(db, "INSERT INTO public.admin_profiles (user_id, role_id) VALUES ($1, $2)", uid, role)
    return {"id": uid, "h": auth_headers(uid, aal="aal2")}


def audit_rows(db: str, action: str):
    return sql(db, "SELECT * FROM public.audit_logs WHERE action = $1 ORDER BY created_at", action)
