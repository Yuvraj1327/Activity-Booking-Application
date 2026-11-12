"""RLS policies, API-role grants and Storage buckets/policies.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-12

Security model (docs/ROLE_PERMISSION_MATRIX.md, decisions D-10..D-12, D-27, D-28):
* FastAPI connects with a privileged role and does ALL writes. RLS is a second layer for
  the case where the Supabase Data API (PostgREST) or a leaked anon/authenticated token
  reaches the database directly.
* anon/authenticated get SELECT only, on specific tables, and only through policies.
  There are NO insert/update/delete policies on application tables.
* Storage: venue-images is public-read and writable only by the backend (no client
  policies). profile-images is private; each user may touch only objects under their own
  `<user_id>/` folder.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = [
    "profiles",
    "customer_profiles",
    "owner_profiles",
    "cities",
    "categories",
    "amenities",
    "venues",
    "venue_categories",
    "venue_amenities",
    "venue_images",
    "venue_resources",
    "notifications",
    "audit_logs",
]
PUBLIC_READ_TABLES = [
    "cities",
    "categories",
    "amenities",
    "venues",
    "venue_categories",
    "venue_amenities",
    "venue_images",
    "venue_resources",
]
UID = "(SELECT auth.uid())"
ROLE = "(SELECT public.app_user_role())"

# (policy name, table, roles, USING expression)
POLICIES: list[tuple[str, str, str, str]] = [
    ("profiles_select_own", "profiles", "authenticated", f"id = {UID}"),
    ("profiles_select_admin", "profiles", "authenticated", f"{ROLE} = 'admin'"),
    ("customer_profiles_select_own", "customer_profiles", "authenticated", f"user_id = {UID}"),
    ("customer_profiles_select_admin", "customer_profiles", "authenticated", f"{ROLE} = 'admin'"),
    ("owner_profiles_select_own", "owner_profiles", "authenticated", f"user_id = {UID}"),
    ("owner_profiles_select_admin", "owner_profiles", "authenticated", f"{ROLE} = 'admin'"),
    ("cities_select_active", "cities", "anon, authenticated", "is_active"),
    ("categories_select_active", "categories", "anon, authenticated", "is_active"),
    ("amenities_select_active", "amenities", "anon, authenticated", "is_active"),
    ("venues_select_published", "venues", "anon, authenticated", "status = 'published'"),
    (
        "venues_select_own",
        "venues",
        "authenticated",
        f"owner_id = {UID} AND {ROLE} = 'owner'",
    ),
    ("venues_select_admin", "venues", "authenticated", f"{ROLE} = 'admin'"),
    # Child tables inherit venue visibility: the sub-select runs under the caller's RLS.
    (
        "venue_categories_select_visible",
        "venue_categories",
        "anon, authenticated",
        "EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id)",
    ),
    (
        "venue_amenities_select_visible",
        "venue_amenities",
        "anon, authenticated",
        "EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id)",
    ),
    (
        "venue_images_select_active",
        "venue_images",
        "anon, authenticated",
        "status = 'active' AND EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id)",
    ),
    (
        "venue_images_select_own",
        "venue_images",
        "authenticated",
        f"{ROLE} = 'owner' AND EXISTS "
        f"(SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = {UID})",
    ),
    (
        "venue_resources_select_active",
        "venue_resources",
        "anon, authenticated",
        "is_active AND EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id)",
    ),
    (
        "venue_resources_select_own",
        "venue_resources",
        "authenticated",
        f"{ROLE} = 'owner' AND EXISTS "
        f"(SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = {UID})",
    ),
    ("notifications_select_own", "notifications", "authenticated", f"user_id = {UID} AND {ROLE} IS NOT NULL"),
    ("audit_logs_select_admin", "audit_logs", "authenticated", f"{ROLE} = 'admin'"),
]

BUCKETS_SQL = """
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types) VALUES
  ('venue-images', 'venue-images', true, 5242880, ARRAY['image/jpeg', 'image/png', 'image/webp']),
  ('profile-images', 'profile-images', false, 2097152, ARRAY['image/jpeg', 'image/png', 'image/webp'])
ON CONFLICT (id) DO UPDATE SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types
"""

# Exactly `<own user id>/<file>.<jpg|jpeg|png|webp>`: no nesting, no `..`, no other user's
# folder. (The bucket's allowed_mime_types and file_size_limit are enforced by Storage.)
OWN_FOLDER = (
    "bucket_id = 'profile-images' "
    "AND name ~ ('^' || (SELECT auth.uid())::text || '/[A-Za-z0-9_-]{1,100}[.](jpg|jpeg|png|webp)$') "
    f"AND {ROLE} IS NOT NULL"
)
STORAGE_POLICIES = [
    ("profile_images_select_own", "SELECT", f"USING ({OWN_FOLDER})"),
    ("profile_images_insert_own", "INSERT", f"WITH CHECK ({OWN_FOLDER})"),
    ("profile_images_update_own", "UPDATE", f"USING ({OWN_FOLDER}) WITH CHECK ({OWN_FOLDER})"),
    ("profile_images_delete_own", "DELETE", f"USING ({OWN_FOLDER})"),
]


def upgrade() -> None:
    # Helper used by policies. SECURITY DEFINER so it can read profiles without recursion;
    # returns NULL for unknown or suspended users, so suspension also closes RLS access.
    op.execute(
        """
CREATE FUNCTION public.app_user_role() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$
  SELECT p.role FROM public.profiles p
  WHERE p.id = (SELECT auth.uid()) AND p.status = 'active'
$$
"""
    )
    op.execute("REVOKE ALL ON FUNCTION public.app_user_role() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.app_user_role() TO anon, authenticated, service_role")

    # Revoke the broad default grants, then give back SELECT only where a policy exists.
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated")

    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT ON public.{table} TO authenticated")
    for table in PUBLIC_READ_TABLES:
        op.execute(f"GRANT SELECT ON public.{table} TO anon")

    for name, table, roles, using in POLICIES:
        op.execute(f"CREATE POLICY {name} ON public.{table} FOR SELECT TO {roles} USING ({using})")

    # Alembic's own bookkeeping table must not be visible to API roles either.
    op.execute("REVOKE ALL ON public.alembic_version FROM anon, authenticated")

    # ---- Storage ---------------------------------------------------------------------------
    op.execute(BUCKETS_SQL)
    for name, command, clause in STORAGE_POLICIES:
        op.execute(f"CREATE POLICY {name} ON storage.objects FOR {command} TO authenticated {clause}")


def downgrade() -> None:
    for name, _command, _clause in STORAGE_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {name} ON storage.objects")
    op.execute("DELETE FROM storage.buckets WHERE id IN ('venue-images', 'profile-images') AND NOT EXISTS (SELECT 1 FROM storage.objects o WHERE o.bucket_id = storage.buckets.id)")
    for name, table, _roles, _using in POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {name} ON public.{table}")
    for table in TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS public.app_user_role()")
