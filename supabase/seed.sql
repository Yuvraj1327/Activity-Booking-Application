-- ============================================================================
-- ZURUV  seed.sql  -  reference data only (categories, amenities, cities)
-- Mirrors backend/scripts/seed_reference_data.py exactly. Run AFTER 001-010.
-- Idempotent: re-running updates names/ordering of categories and amenities and adds only
-- missing cities. It never deletes anything and never touches users, venues or bookings.
-- The city list is an India-first assumption (open question N1): review it before launch.
-- There is NO demo data here (demo venues need a real owner account; see
-- backend/scripts/seed_demo_venues.py, development only).
-- ============================================================================

BEGIN;

INSERT INTO public.categories (slug, name, icon_key, sort_order) VALUES
  ('badminton', 'Badminton', 'badminton', 1),
  ('tennis', 'Tennis', 'tennis', 2),
  ('swimming', 'Swimming', 'swimming', 3),
  ('gym', 'Gym', 'gym', 4),
  ('yoga', 'Yoga', 'yoga', 5),
  ('cricket', 'Cricket', 'cricket', 6),
  ('football', 'Football', 'football', 7),
  ('basketball', 'Basketball', 'basketball', 8),
  ('table-tennis', 'Table Tennis', 'table_tennis', 9),
  ('squash', 'Squash', 'squash', 10),
  ('snooker', 'Snooker', 'snooker', 11),
  ('pickleball', 'Pickleball', 'pickleball', 12)
ON CONFLICT (slug) DO UPDATE SET
  name = EXCLUDED.name, icon_key = EXCLUDED.icon_key, sort_order = EXCLUDED.sort_order;

INSERT INTO public.amenities (slug, name, icon_key, sort_order) VALUES
  ('parking', 'Parking', 'parking', 1),
  ('changing-room', 'Changing Room', 'changing_room', 2),
  ('shower', 'Shower', 'shower', 3),
  ('drinking-water', 'Drinking Water', 'water', 4),
  ('floodlights', 'Floodlights', 'floodlights', 5),
  ('equipment-rental', 'Equipment Rental', 'equipment', 6),
  ('first-aid', 'First Aid', 'first_aid', 7),
  ('cafe', 'Café', 'cafe', 8),
  ('wifi', 'Wi-Fi', 'wifi', 9),
  ('lockers', 'Lockers', 'lockers', 10),
  ('washroom', 'Washroom', 'washroom', 11),
  ('air-conditioning', 'Air Conditioning', 'ac', 12)
ON CONFLICT (slug) DO UPDATE SET
  name = EXCLUDED.name, icon_key = EXCLUDED.icon_key, sort_order = EXCLUDED.sort_order;

INSERT INTO public.cities (name, state, country_code)
SELECT v.name, v.state, 'IN'
FROM (VALUES
  ('Bengaluru', 'Karnataka'),
  ('Mumbai', 'Maharashtra'),
  ('Delhi', 'Delhi'),
  ('Hyderabad', 'Telangana'),
  ('Chennai', 'Tamil Nadu'),
  ('Pune', 'Maharashtra'),
  ('Kolkata', 'West Bengal'),
  ('Ahmedabad', 'Gujarat'),
  ('Gurugram', 'Haryana'),
  ('Jaipur', 'Rajasthan')
) AS v(name, state)
WHERE NOT EXISTS (
  SELECT 1 FROM public.cities c WHERE lower(c.name) = lower(v.name) AND c.country_code = 'IN'
);

COMMIT;
