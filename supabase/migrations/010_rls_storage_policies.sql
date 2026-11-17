-- ============================================================================
-- ZURUV  010_rls_storage_policies
-- Alembic equivalent : revisions 0003, 0004, 0005, 0006, 0007, 0009 (RLS, grants, policies, storage), Alembic stamp
-- Requires           : 002-009 (all tables exist)
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- Security model    : RLS is ON for every application table. anon/authenticated get SELECT only,
--                    through the policies below. All writes go through the FastAPI backend.
-- ============================================================================

BEGIN;

-- Revoke every default privilege from the Supabase API roles, then grant back exactly what
-- the data API may read. The FastAPI backend connects as the database owner and is not
-- affected. Writes are never granted to anon/authenticated.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;

-- ---- Row Level Security + read grants (revisions 0003-0009) ----
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.profiles TO authenticated;

ALTER TABLE public.customer_profiles ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.customer_profiles TO authenticated;

ALTER TABLE public.owner_profiles ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.owner_profiles TO authenticated;

ALTER TABLE public.cities ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.cities TO authenticated;

ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.categories TO authenticated;

ALTER TABLE public.amenities ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.amenities TO authenticated;

ALTER TABLE public.venues ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.venues TO authenticated;

ALTER TABLE public.venue_categories ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.venue_categories TO authenticated;

ALTER TABLE public.venue_amenities ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.venue_amenities TO authenticated;

ALTER TABLE public.venue_images ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.venue_images TO authenticated;

ALTER TABLE public.venue_resources ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.venue_resources TO authenticated;

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.notifications TO authenticated;

ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.audit_logs TO authenticated;

GRANT SELECT ON public.cities TO anon;

GRANT SELECT ON public.categories TO anon;

GRANT SELECT ON public.amenities TO anon;

GRANT SELECT ON public.venues TO anon;

GRANT SELECT ON public.venue_categories TO anon;

GRANT SELECT ON public.venue_amenities TO anon;

GRANT SELECT ON public.venue_images TO anon;

GRANT SELECT ON public.venue_resources TO anon;

ALTER TABLE public.favorites ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.favorites FROM anon, authenticated;

GRANT SELECT ON public.favorites TO authenticated;

ALTER TABLE public.schedule_rules ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.schedule_exceptions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.schedule_rules, public.schedule_exceptions FROM anon, authenticated;

GRANT SELECT ON public.schedule_rules, public.schedule_exceptions TO authenticated;

ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.booking_slots ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.booking_status_history ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.availability_blocks ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.bookings, public.booking_slots, public.booking_status_history, public.availability_blocks FROM anon, authenticated;

GRANT SELECT ON public.bookings, public.booking_slots, public.booking_status_history, public.availability_blocks TO authenticated;

ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.payment_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.user_device_tokens ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.email_deliveries ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.payments, public.payment_events, public.user_device_tokens, public.notification_preferences, public.email_deliveries FROM anon, authenticated;

GRANT SELECT ON public.payments, public.notification_preferences TO authenticated;

ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.review_responses ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.reviews, public.review_responses FROM anon, authenticated;

-- ---- Policies ----
CREATE POLICY profiles_select_own ON public.profiles FOR SELECT TO authenticated USING (id = (SELECT auth.uid()));

CREATE POLICY profiles_select_admin ON public.profiles FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'admin');

CREATE POLICY customer_profiles_select_own ON public.customer_profiles FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()));

CREATE POLICY customer_profiles_select_admin ON public.customer_profiles FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'admin');

CREATE POLICY owner_profiles_select_own ON public.owner_profiles FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()));

CREATE POLICY owner_profiles_select_admin ON public.owner_profiles FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'admin');

CREATE POLICY cities_select_active ON public.cities FOR SELECT TO anon, authenticated USING (is_active);

CREATE POLICY categories_select_active ON public.categories FOR SELECT TO anon, authenticated USING (is_active);

CREATE POLICY amenities_select_active ON public.amenities FOR SELECT TO anon, authenticated USING (is_active);

CREATE POLICY venues_select_published ON public.venues FOR SELECT TO anon, authenticated USING (status = 'published');

CREATE POLICY venues_select_own ON public.venues FOR SELECT TO authenticated USING (owner_id = (SELECT auth.uid()) AND (SELECT public.app_user_role()) = 'owner');

CREATE POLICY venues_select_admin ON public.venues FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'admin');

CREATE POLICY venue_categories_select_visible ON public.venue_categories FOR SELECT TO anon, authenticated USING (EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id));

CREATE POLICY venue_amenities_select_visible ON public.venue_amenities FOR SELECT TO anon, authenticated USING (EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id));

CREATE POLICY venue_images_select_active ON public.venue_images FOR SELECT TO anon, authenticated USING (status = 'active' AND EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id));

CREATE POLICY venue_images_select_own ON public.venue_images FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'owner' AND EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = (SELECT auth.uid())));

CREATE POLICY venue_resources_select_active ON public.venue_resources FOR SELECT TO anon, authenticated USING (is_active AND EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id));

CREATE POLICY venue_resources_select_own ON public.venue_resources FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'owner' AND EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = (SELECT auth.uid())));

CREATE POLICY notifications_select_own ON public.notifications FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()) AND (SELECT public.app_user_role()) IS NOT NULL);

CREATE POLICY audit_logs_select_admin ON public.audit_logs FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'admin');

CREATE POLICY favorites_select_own ON public.favorites FOR SELECT TO authenticated USING (customer_id = (SELECT auth.uid()) AND (SELECT public.app_user_role()) = 'customer');

CREATE POLICY schedule_rules_select ON public.schedule_rules FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id));

CREATE POLICY schedule_exceptions_select ON public.schedule_exceptions FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id));

CREATE POLICY bookings_select_own ON public.bookings FOR SELECT TO authenticated USING (customer_id = (SELECT auth.uid()));

CREATE POLICY bookings_select_owner ON public.bookings FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'owner' AND EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = (SELECT auth.uid())));

CREATE POLICY bookings_select_admin ON public.bookings FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'admin');

CREATE POLICY booking_slots_select ON public.booking_slots FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM public.bookings b WHERE b.id = booking_id));

CREATE POLICY bsh_select ON public.booking_status_history FOR SELECT TO authenticated USING (EXISTS (SELECT 1 FROM public.bookings b WHERE b.id = booking_id));

CREATE POLICY blocks_select_owner ON public.availability_blocks FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'owner' AND EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = (SELECT auth.uid())));

CREATE POLICY blocks_select_admin ON public.availability_blocks FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'admin');

CREATE POLICY payments_select_own ON public.payments FOR SELECT TO authenticated USING (customer_id = (SELECT auth.uid()));

CREATE POLICY payments_select_owner ON public.payments FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'owner' AND EXISTS (SELECT 1 FROM public.venues v WHERE v.id = venue_id AND v.owner_id = (SELECT auth.uid())));

CREATE POLICY payments_select_admin ON public.payments FOR SELECT TO authenticated USING ((SELECT public.app_user_role()) = 'admin');

CREATE POLICY notification_preferences_select_own ON public.notification_preferences FOR SELECT TO authenticated USING (user_id = (SELECT auth.uid()));

-- ---- Storage buckets and policies (revision 0003) ----
-- venue-images is public-read; uploads/deletes go through the backend (service role).
-- profile-images is private; each user may only touch objects under their own uid folder.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types) VALUES
  ('venue-images', 'venue-images', true, 5242880, ARRAY['image/jpeg', 'image/png', 'image/webp']),
  ('profile-images', 'profile-images', false, 2097152, ARRAY['image/jpeg', 'image/png', 'image/webp'])
ON CONFLICT (id) DO UPDATE SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

CREATE POLICY profile_images_select_own ON storage.objects FOR SELECT TO authenticated USING (bucket_id = 'profile-images' AND name ~ ('^' || (SELECT auth.uid())::text || '/[A-Za-z0-9_-]{1,100}[.](jpg|jpeg|png|webp)$') AND (SELECT public.app_user_role()) IS NOT NULL);

CREATE POLICY profile_images_insert_own ON storage.objects FOR INSERT TO authenticated WITH CHECK (bucket_id = 'profile-images' AND name ~ ('^' || (SELECT auth.uid())::text || '/[A-Za-z0-9_-]{1,100}[.](jpg|jpeg|png|webp)$') AND (SELECT public.app_user_role()) IS NOT NULL);

CREATE POLICY profile_images_update_own ON storage.objects FOR UPDATE TO authenticated USING (bucket_id = 'profile-images' AND name ~ ('^' || (SELECT auth.uid())::text || '/[A-Za-z0-9_-]{1,100}[.](jpg|jpeg|png|webp)$') AND (SELECT public.app_user_role()) IS NOT NULL) WITH CHECK (bucket_id = 'profile-images' AND name ~ ('^' || (SELECT auth.uid())::text || '/[A-Za-z0-9_-]{1,100}[.](jpg|jpeg|png|webp)$') AND (SELECT public.app_user_role()) IS NOT NULL);

CREATE POLICY profile_images_delete_own ON storage.objects FOR DELETE TO authenticated USING (bucket_id = 'profile-images' AND name ~ ('^' || (SELECT auth.uid())::text || '/[A-Za-z0-9_-]{1,100}[.](jpg|jpeg|png|webp)$') AND (SELECT public.app_user_role()) IS NOT NULL);

-- ---- Alembic bookkeeping ----
-- Marks this database as being at Alembic head (0009) so `alembic upgrade head` from the
-- backend is a no-op instead of trying to create everything again. An existing, non-empty
-- alembic_version table is never modified.
CREATE TABLE IF NOT EXISTS public.alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

INSERT INTO public.alembic_version (version_num)
SELECT '0009' WHERE NOT EXISTS (SELECT 1 FROM public.alembic_version);

REVOKE ALL ON public.alembic_version FROM anon, authenticated;

COMMIT;
