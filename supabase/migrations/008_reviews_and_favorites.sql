-- ============================================================================
-- ZURUV  008_reviews_and_favorites
-- Alembic equivalent : revisions 0004 (favorites), 0009 (reviews, replies, rating trigger)
-- Requires           : 005 (reviews reference bookings)
-- Safe to run        : once, on a fresh Supabase project. Runs in one transaction;
--                      if any statement fails nothing from this file is applied.
--                      Contains no DROP/TRUNCATE/DELETE of existing data.
-- ============================================================================

BEGIN;

CREATE TABLE public.favorites (
  customer_id uuid NOT NULL REFERENCES public.customer_profiles (user_id) ON DELETE CASCADE,
  venue_id uuid NOT NULL REFERENCES public.venues (id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_favorites PRIMARY KEY (customer_id, venue_id)
);

CREATE INDEX ix_favorites_customer_created ON public.favorites (customer_id, created_at DESC);

CREATE INDEX ix_favorites_venue_id ON public.favorites (venue_id);

CREATE TABLE public.reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE RESTRICT,
  venue_id uuid NOT NULL REFERENCES public.venues(id) ON DELETE RESTRICT,
  customer_id uuid NOT NULL REFERENCES public.customer_profiles(user_id) ON DELETE RESTRICT,
  rating smallint NOT NULL,
  comment text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_reviews_booking UNIQUE (booking_id),
  CONSTRAINT ck_reviews_rating CHECK (rating BETWEEN 1 AND 5),
  CONSTRAINT ck_reviews_comment CHECK (comment IS NULL OR char_length(comment) BETWEEN 1 AND 1000)
);

CREATE TABLE public.review_responses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id uuid NOT NULL REFERENCES public.reviews(id) ON DELETE RESTRICT,
  owner_id uuid NOT NULL REFERENCES public.owner_profiles(user_id) ON DELETE RESTRICT,
  body text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_review_responses_review UNIQUE (review_id),
  CONSTRAINT ck_review_responses_body CHECK (char_length(body) BETWEEN 1 AND 1000)
);

CREATE INDEX ix_reviews_venue_created ON public.reviews (venue_id, created_at DESC);

CREATE INDEX ix_reviews_customer ON public.reviews (customer_id);

CREATE FUNCTION public.refresh_venue_rating() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM 1 FROM public.venues WHERE id = NEW.venue_id FOR UPDATE;
  UPDATE public.venues v
     SET rating_count = s.c, rating_avg = s.a
    FROM (SELECT count(*)::int AS c, round(avg(rating)::numeric, 1) AS a
            FROM public.reviews WHERE venue_id = NEW.venue_id) s
   WHERE v.id = NEW.venue_id;
  RETURN NEW;
END
$$;

CREATE TRIGGER trg_reviews_rating AFTER INSERT ON public.reviews FOR EACH ROW EXECUTE FUNCTION public.refresh_venue_rating();

CREATE FUNCTION public.reviews_are_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'reviews and replies cannot be changed or deleted' USING ERRCODE = '23000';
END
$$;

CREATE TRIGGER trg_reviews_immutable BEFORE UPDATE OR DELETE ON public.reviews FOR EACH ROW EXECUTE FUNCTION public.reviews_are_immutable();

CREATE TRIGGER trg_review_responses_immutable BEFORE UPDATE OR DELETE ON public.review_responses FOR EACH ROW EXECUTE FUNCTION public.reviews_are_immutable();

COMMIT;
