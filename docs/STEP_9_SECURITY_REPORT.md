# Step 9 security report

| Area | How checked | Result |
|---|---|---|
| Invalid, expired, wrong-audience, wrong-issuer, bad-signature, `alg:none`, missing-subject JWTs | `test_security.py` (existing) and live smoke | Rejected (401) |
| Customer and owner blocked from admin APIs | 16 paths, MFA on | 403 |
| Customer blocked from owner APIs; owner blocked from another owner's venue and bookings | existing plus new tests | 403 / 404, nothing changed |
| Customer cannot read another customer's booking or payment | new test | 404 |
| Users cannot assign themselves admin | role/status/id/email in a body rejected (422); DB trigger blocks role changes; admins only via operator script | Passed (existing) |
| RLS and storage policies | `test_rls.py`, `test_storage_policies.py` on a local Postgres with a Supabase stub | Passed. **Not tested on real Supabase.** |
| Admin cannot suspend self or other admins; status changes and exports audited | Step 8 tests | Passed |
| SQL injection | Parameterised queries throughout; 6 hostile strings against 6 list endpoints | No error, no effect; LIKE wildcards escaped |
| Upload validation | Size limit, magic-byte type check, image count cap, suspended users blocked (existing tests) | Passed |
| Price tampering | A client-sent price is rejected with 422; amount always comes from the booking row | Passed |
| Payment and webhook integrity | See test report | Passed against fakes |
| Secrets in client code or Git | `scripts/scan_secrets.py` over the repo and the built admin bundle; `.gitignore` covers `.env`, `env/*.json`, keys, Firebase files | Clean. **Git has no commits yet**, so history was not scanned. |
| Service-role key in clients | Name scan of client source directories; only the backend reads it | Not present |
| CORS | New test and live smoke | Only configured origins |
| Rate limiting | **Added in Step 9** (was missing): 60 requests per minute per client per group (payments, booking writes, quotes, profile creation, image upload, CSV export); 429 with `Retry-After` | Passed. Limits below. |

## Findings fixed in Step 9

1. **No rate limiting existed.** Added `app/core/ratelimit.py` (setting `RATE_LIMIT_PER_MINUTE`, `0` disables).
2. **Release builds could silently use `localhost`.** The Flutter shared config and the admin web fell back to a localhost API URL. Flutter now throws if `API_BASE_URL` is missing outside debug; the admin web treats a production build with no API URL as not configured.

## Remaining security notes

- The limiter is in-process and keyed by the TCP peer address. With several workers the effective limit multiplies; behind a proxy all clients may share one address unless the proxy forwards real addresses. A shared store (Redis) is the proper production fix, not added here. Authentication endpoints are Supabase's, so their throttling is Supabase's responsibility and was not tested.
- Unauthenticated requests to limited paths count toward the limit, which is intended.
- Admin MFA is enforced in staging and production by default, but was only tested with synthetic `aal2` tokens.
- Real-credential handling (Razorpay, Firebase, Resend) was not exercised.
- Mobile app storage of tokens and certificate handling were not reviewed (no SDK).
