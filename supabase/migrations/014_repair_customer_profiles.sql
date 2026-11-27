-- ============================================================================
-- ZURUV  014_repair_customer_profiles
-- Alembic equivalent : revision 0013
-- Requires           : 013 (and all earlier files)
-- Safe to run        : any number of times for the data change (it inserts only missing rows). Runs in
--                      one transaction; contains no DROP/TRUNCATE/DELETE/UPDATE of existing data.
-- Fixes              : customers that have a profiles row but no customer_profiles row, which made
--                      POST /bookings fail with the foreign key bookings_customer_id_fkey.
-- Check (expect 0 after): SELECT count(*) FROM public.profiles p WHERE p.role = 'customer'
--                           AND NOT EXISTS (SELECT 1 FROM public.customer_profiles c WHERE c.user_id = p.id);
-- ============================================================================

BEGIN;

INSERT INTO public.customer_profiles (user_id, role)
SELECT p.id, p.role
FROM public.profiles p
WHERE p.role = 'customer'
  AND NOT EXISTS (SELECT 1 FROM public.customer_profiles c WHERE c.user_id = p.id)
ON CONFLICT (user_id) DO NOTHING;

UPDATE public.alembic_version SET version_num = '0013' WHERE version_num = '0012';

COMMIT;
