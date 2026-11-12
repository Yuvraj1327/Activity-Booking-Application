# Availability logic (Step 6)

Availability is computed **only on the backend** (`app/domain/slot_engine.py`, `app/services/availability.py`). The apps display what the API returns and never work out a slot themselves.

## Inputs

| Input | Source | Notes |
|---|---|---|
| Weekly hours | `schedule_rules` | Local venue time, `weekday` 0 = Monday, several intervals per day allowed |
| Special dates | `schedule_exceptions` | A date **replaces** the weekly hours for that date: closed, or custom hours (Q16 precedence) |
| Courts | `venue_resources` | Each active court has `slot_minutes` and `slot_price_paise`, both set by the owner |
| Blocked periods | `availability_blocks` | Owner-set temporary unavailability, for one court or the whole venue |
| Reservations | `booking_slots` | Only rows that block (`pending_payment`, `payment_failed`, `confirmed`); a hold past `expires_at` is ignored |
| Time zone | `venues.timezone` (IANA) | All wall-clock rules are evaluated in the venue's zone, all stored instants are UTC |
| Optional window | `BOOKING_MIN_NOTICE_MINUTES`, `BOOKING_MAX_ADVANCE_DAYS` | Off unless configured (N6) |

## Algorithm for one court on one date

1. `plan_day`: special date if one exists (closed → no slots; custom hours → those hours), else the weekly intervals for that weekday (none → closed).
2. `generate_windows`: for every interval, start at the opening time and step by `slot_minutes`; a window must end at or before closing. The remainder at the end of an interval is unused. Nothing can cross closing time, so out-of-hours slots cannot exist.
3. Convert each local start/end to UTC. A wall time that does not exist (spring-forward gap) or is ambiguous (fall-back overlap) is **skipped**, never guessed.
4. `filter_available`: drop windows that already started, windows inside the minimum notice, windows beyond the maximum advance, and any window that **overlaps** a reservation or block (back-to-back slots do not overlap).
5. The API returns only the surviving windows, plus the court's `state`:

| `state` | Meaning |
|---|---|
| `available` | At least one free slot |
| `fully_booked` | Open, but nothing left |
| `closed` | Closed that weekday or date (`closed_reason`: `weekly_closed`, `special_closure`) |
| `not_configured` | The court has no slot length or price yet, so it has no slots |

`GET /venues/{id}/availability/dates` repeats this for up to 31 days and returns the dates with at least one free slot on any court (the customer date strip uses the same endpoint rules).

## Example

Venue open 06:00–22:00 (Asia/Kolkata), Court 1 = 60-minute slots at ₹500, one booking at 09:00 on 2030-01-07:

```json
GET /api/v1/venues/<venue>/availability?date=2030-01-07
{
  "venue_id": "…", "date": "2030-01-07", "timezone": "Asia/Kolkata",
  "closed_reason": null, "note": null,
  "resources": [{
    "resource_id": "…", "name": "Court 1", "slot_minutes": 60, "slot_price_paise": 50000,
    "currency": "INR", "state": "available", "message": null,
    "slots": [
      {"starts_at": "2030-01-07T00:30:00Z", "ends_at": "2030-01-07T01:30:00Z",
       "local_start": "06:00", "local_end": "07:00", "price_paise": 50000}
      /* … 08:00 and 10:00 … 21:00; 09:00 is absent */
    ]
  }]
}
```

## Prevented by construction

| Problem | How it is prevented |
|---|---|
| Out-of-hours slot | Windows are generated inside opening intervals; a booking request must equal a generated window exactly (`422 INVALID_SLOT`) |
| Invalid duration | Duration is always the court's `slot_minutes`; clients send only `resource_id` and `starts_at` |
| Overlap | Revalidated inside the booking transaction, then enforced by the database (see `BOOKING_ENGINE.md`) |
| Unavailable court | Inactive or unconfigured courts have no slots and cannot be booked (`409 RESOURCE_NOT_CONFIGURED`) |
| Past or too-late slot | `filter_available` and the same check inside the booking transaction (`422 SLOT_NOT_BOOKABLE`) |
| Time-zone mix-ups | Venue-local rules, UTC storage, DST-ambiguous times skipped; `starts_at` must carry an offset |

## Schedule changes vs. existing bookings (Q16)

An owner change to weekly hours, special dates, a court's slot length or active flag, a blocked period, or the venue time zone is applied, then checked against every **future blocking booking**: each must still equal a generated window and not lie in a block. If any would break, the whole change is rolled back and refused:

```json
409 {"code":"SCHEDULE_CONFLICT","message":"This change would affect existing bookings. Nothing was changed.",
     "details":{"count":2,"bookings":[{"booking_code":"ZUR-…","starts_at":"…","ends_at":"…","status":"confirmed"}]}}
```

Bookings are **never cancelled automatically**. Changes that cannot break a booking (price, other dates, other hours) succeed. Price changes never touch an existing booking because its price is snapshotted at creation. This is the architecture's default; the business can still choose another policy (Q16).

## Not built (needs an answer first)

Time-of-day or weekend pricing, peak/off-peak, discounts (Q7/Q8/N7); variable durations or multi-slot bookings (N2); automatic court assignment (N3); capacity / class bookings (N23); recurring blocks; per-court opening hours.
