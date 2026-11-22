"""Promote an EXISTING Supabase auth user to ADMIN. Operator tool; never exposed over HTTP.

Admins cannot be created through the public API (decision D-24). Steps:
  1. Create the user in the Supabase dashboard (Authentication > Users > Add user), or have
     them sign up, with a strong password. Enrol TOTP on first admin-web login.
  2. Run, from backend/ with DATABASE_URL pointing at the project (direct connection):

       python -m scripts.create_admin --email admin@example.com --name "Admin Name" --role super_admin

     Without --role the account has NO permissions. The first administrator needs --role super_admin;
     later ones are given a role from the admin panel (Admin roles).

The script only reads auth.users and writes profiles + audit_logs. It needs no service-role key.
"""

import argparse
import asyncio
import sys

import asyncpg

from app.core.config import get_settings


async def promote(dsn: str, email: str, name: str, role: str | None = None) -> str:
    conn = await asyncpg.connect(dsn, statement_cache_size=0)
    try:
        async with conn.transaction():
            user = await conn.fetchrow("SELECT id FROM auth.users WHERE lower(email) = lower($1)", email)
            if user is None:
                raise SystemExit(f"No auth user with e-mail {email!r}. Create it in Supabase first.")
            role_row = None
            if role is not None:
                role_row = await conn.fetchrow("SELECT id FROM public.admin_roles WHERE name = $1", role)
                if role_row is None:
                    raise SystemExit(f"No admin role named {role!r}. Create it in the admin panel first.")
            existing = await conn.fetchrow("SELECT role FROM public.profiles WHERE id = $1", user["id"])
            if existing is not None:
                if existing["role"] == "admin":
                    return f"{email} is already an admin; nothing changed."
                raise SystemExit(
                    f"{email} already has a {existing['role']} profile. Roles are immutable: "
                    "use a different account for the admin."
                )
            await conn.execute(
                "INSERT INTO public.profiles (id, role, full_name, email) VALUES ($1, 'admin', $2, lower($3))",
                user["id"], name, email,
            )  # fmt: skip
            await conn.execute(
                "INSERT INTO public.audit_logs (actor_id, actor_role, action, entity_type, entity_id, metadata) "
                "VALUES (NULL, 'system', 'admin.created', 'profile', $1, '{\"via\": \"scripts.create_admin\"}'::jsonb)",
                str(user["id"]),
            )
            if role_row is not None:
                await conn.execute(
                    "INSERT INTO public.admin_profiles (user_id, role_id) VALUES ($1, $2)",
                    user["id"],
                    role_row["id"],
                )
                return f"{email} is now an admin with the {role!r} role."
            return (
                f"{email} is now an admin with NO role: they can sign in but see nothing until "
                "a roles.manage administrator assigns one."
            )
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument(
        "--role",
        default=None,
        help="Optional admin role to assign (e.g. super_admin for the FIRST administrator). "
        "Without it the new admin has no permissions.",
    )
    args = parser.parse_args()
    settings = get_settings()
    secret = settings.alembic_database_url or settings.database_url
    if secret is None:
        sys.exit("No database configured: set DATABASE_URL (or ALEMBIC_DATABASE_URL) in backend/.env")
    dsn = secret.get_secret_value().replace("postgresql+asyncpg://", "postgresql://")
    print(asyncio.run(promote(dsn, args.email, args.name, args.role)))


if __name__ == "__main__":
    main()
