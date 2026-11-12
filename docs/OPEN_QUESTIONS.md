# ZURUV — OPEN QUESTIONS

Legend — **Blocker:** must be answered before the stated stage starts. **Soon:** answer before the stated stage is finished. **Later:** can follow a documented default.
`Roadmap stage` numbers refer to the 16 stages in `IMPLEMENTATION_ROADMAP.md`.

---

## Coverage of the topics required for Stage 1

Every item below is explained further, with why it matters, in the sections that follow.

| Topic | Where answered | Status |
|---|---|---|
| Venue vs activity booking model | Q1, N23 | Open (**Blocker**) |
| Individual court/resource booking | Q2, Q17, C2, N2, N3 | Open (**Blocker**) |
| Single or multiple mobile applications | Q3 | **Resolved**: two separate Flutter apps in one monorepo, per the instruction to keep separate Customer and Owner experiences |
| Venue approval workflow | Q4, C1 | Open |
| Payment gateway configuration | Q5, Q6, N25, S2-4 | Razorpay approved; country and requirements pending |
| Platform commission | Q8, C6 | Open (**Blocker**) |
| GST and platform fees | Q7, C6, C7 | Open (**Blocker**) |
| Cancellation and refund policy | Q9, N22, C10 | Open (**Blocker**) |
| Owner payout process | Q10, N11 | Open |
| Booking status transitions | Q11 | Open (**Blocker**); proposal in `SYSTEM_ARCHITECTURE.md` §9.4 |
| Location and map requirements | Q12, Q13 | Q13 resolved (Google Maps); Q12 open |
| Notification channels | Q14, N24 | Push (FCM) and email (Resend) approved; SMS/WhatsApp not approved |
| Admin permissions | Q18, N12, N13 | Open |

---

## A. Source gaps (resolve first)

| ID | Issue | Needed from client |
|---|---|---|
| S1 | `quotation.pdf` was not available. Scope, deliverables, vendor/customer responsibilities and admin requirements are unverified against it. | Provide the PDF. |
| S2 | `app-walkthrough.mp4` was not available. Behavioural details and any screens/flows beyond the boards are unknown. | Provide the video. |
| S3 | No repository or technical requirements supplied. Stack is unconstrained. | Confirm greenfield, or supply repo and any mandated stack/hosting. |
| S4 | UI boards are compressed screenshots, not design files. Exact colours, fonts, spacing and assets cannot be extracted reliably. | Provide Figma/source files or original-resolution assets, logo, and photography licences. |

---

## B. Conflicts and inconsistencies between sources

| ID | Conflict | Sources | Proposed handling until answered |
|---|---|---|---|
| C1 | Brief says admin does not manage owners' listings, yet the Owner board shows a venue in **"Pending"** status (AquaLife), implying an approval step. | Brief §3B/§3C vs O-S5; Q4 | Model venue status (`draft`, `pending`, `active`, `inactive`, `suspended`) but implement **no** approval gate; new venues go live per Q4 answer. Do not give admin ownership of listings. |
| C2 | Owner board shows "Court 1" and "2 Courts • 1 hour" (multi-resource, multi-court bookings). Customer board has no court-selection step and summary says "Court Charges". | O-S8, O-S9 vs C-S6–C-S8; Q1, Q2, Q17 | Design schema with a `resources` table (a single-resource venue = one default resource). Do not build court-selection UI until answered. |
| C3 | Brief §10 requires "booking changes" rules, but no reschedule/modify screen exists in either board. | Brief §10 vs C-S11 | Treat reschedule as **out of scope** unless confirmed; only cancel is supported. |
| C4 | Brief requires owner venue **pricing, facilities, amenities, location (map)** and slot **duration/pricing**, and **review responses**; the boards show none of these controls. Special Hours tab is also not shown. | Brief §5 S6/S7/S12 vs O-S6, O-S7, O-S12 | Screens must be designed to the brief; flag as "design needed". |
| C5 | Several taglines: brand "Discover. Book. Play."; customer splash "Play More. Live Better."; customer onboarding "Your City. More to Play."; owner splash "More Players. More Possibilities."; owner onboarding "List Your Venue. Reach More Players."; owner board header "Manage. Grow. Welcome More Players." | Brief §1, §4 vs boards | Use "Discover. Book. Play." as brand tagline; treat per-screen lines as screen copy as drawn. Confirm. |
| C6 | Customer pays ₹496 (₹400 court + ₹20 platform fee + ₹76 GST), but owner board shows booking "Total Amount ₹400" and earnings ₹400 per booking. What the owner sees/earns (gross, net of commission, excl. GST) is undefined. | C-S8 vs O-S9, O-S10; Q7, Q8 | Store every component separately (base, fee, tax, discount, commission, owner share). UI labels wait for Q7/Q8. |
| C7 | Board arithmetic: GST 18% of ₹76 equals 18% of (₹400 + ₹20) = ₹75.60 rounded to ₹76, i.e. GST is shown applied to the platform fee as well as the court charge. This is an illustration, not a rule. | C-S8; Q7 | Compute from configurable, versioned rules; rounding mode to be specified (Q7). |
| C8 | Owner bottom nav has 5 tabs (Dashboard, Venues, Bookings, Payments, More) while the brief lists 14 owner screens; placement of Analytics/Reviews/Notifications/Profile is not shown. | O-S4–O-S14 | Assume under "More"; confirm. |
| C9 | Customer venue-detail board has a **share** action not in the brief. | C-S6 | Not built unless confirmed (brief: "do not invent features"). |
| C10 | Owner "Cancel Booking" button exists, but brief only lists owner capability to *monitor* statuses and says actions follow cancellation rules. | O-S9; Q9, Q11 | Disabled behind feature flag until cancellation/refund policy is confirmed. |
| C11 | Categories differ: customer Home shows 8 (Badminton, Tennis, Swimming, Gym, Yoga, Cricket, Football, More); owner Add Venue shows 5 (Badminton, Tennis, Swimming, Gym, More). Nobody is assigned to manage the category list; admin scope in brief omits master data. | C-S4 vs O-S6; Brief §6 | Categories (and amenities) are data-driven master data. Who edits them (admin?) needs confirmation. |
| C12 | Mock dates (27 Oct 2026, 28 Oct, etc.) are in the past relative to today (12 Nov 2026). | C-S7, C-S11 | Treated as placeholder content only. |
| C13 | Wallet is shown as "Wallet (if available)". | C-S9 vs Q6 | Not built unless confirmed. |
| C14 | Customer board has no "write a review" flow, though the venue and owner views show reviews and Q15 asks who may review. | C-S6, O-S12 | Review submission UI needs design once Q15 answered. |
| C15 | Customer slot grid shows start times only, skips 12:00–4:00 PM and 8:00 PM, shows 9:00 PM twice, while owner hours are 6:00 AM–11:00 PM. This is either a mock-up error or it means unavailable slots are **hidden** rather than shown disabled. | C-S7 vs O-S7; Brief §4 S7 | Treat as a design error. Slot display (hide vs disable unavailable slots, end time shown) is confirmed with the design review before the Stage 6 UI. |
| C16 | Brief asks owners to "select venue categories" (plural); the Add Venue board shows one row of category icons with a single highlighted selection. | Brief §5 S6 vs O-S6 | Data model supports many categories per venue; UI selection mode to be confirmed. |

---

## C. Business decisions from the brief (Q1–Q18)

| ID | Question | Why it matters | Needed before | Priority |
|---|---|---|---|---|
| Q1 | Is the primary bookable item a venue, a court/resource within a venue, an activity, or a combination? | Core data model and availability logic. Boards suggest courts (C2). | Stage 3 (DB design) | **Blocker** |
| Q2 | Does a customer book an entire venue or individual courts/slots? | Same; affects pricing and conflict rules. | Stage 3 | **Blocker** |
| Q3 | Two separate mobile apps or one role-based app? | Project structure, store listings, auth, release process. Recommendation in architecture doc: two apps from one monorepo. | Stage 2 | **Blocker** |
| Q4 | Is new venue publishing immediate, or does admin approve? | Venue status machine, admin scope, owner expectations (C1). | Stage 5 | Soon |
| Q5 | Which payment gateway? | Integration design, payout capability, fees, KYC. Recommendation: evaluate Razorpay given INR and UPI. | Stage 3 (payments schema), Stage 7 | **Blocker** |
| Q6 | Is wallet payment in scope? | Payment UI and provider support. | Stage 7 | Later |
| Q7 | Platform fee and tax rules (rates, base, rounding, who is the taxable supplier, invoicing)? | Pricing engine, summary screen, reporting. Needs tax/accounting advice. | Stage 6 | **Blocker** |
| Q8 | Owner commission / platform revenue model? | Earnings, payouts, admin revenue figures. | Stage 6 | **Blocker** |
| Q9 | Cancellation and refund policy (windows, percentages, who can cancel, gateway-fee treatment)? | Booking state machine, refund flow, UI copy. | Stage 6 | **Blocker** |
| Q10 | How and when are owners paid (schedule, thresholds, method, KYC, holds, disputes)? | Payout schema, provider choice, owner earnings screens. | Stage 8 | Soon |
| Q11 | Exact booking statuses and permitted transitions? | Consistency across three apps. A proposal is in architecture doc §6.5. | Stage 3 | **Blocker** |
| Q12 | Is location-based discovery required (Near Me, distance)? | Needs coordinates, permission flows, geo queries. Boards show "Near me" and "2.4 km". | Stage 4 | Soon |
| Q13 | Which map/location provider? | Cost, keys, address autocomplete, geocoding. | Stage 4 | Soon |
| Q14 | Notification channels: push, email, SMS, WhatsApp? | Provider contracts, templates, DLT/WhatsApp approvals. | Stage 7 | Soon |
| Q15 | May reviews be written only after completed bookings? | Review integrity rules, DB constraints. | Stage 8 | Soon |
| Q16 | May special hours override existing bookings? | Conflict handling; may require cancelling/refunding customers. | Stage 6 | **Blocker** |
| Q17 | Are multiple resources/courts supported in one venue? | See Q1; also "2 Courts" bookings. | Stage 3 | **Blocker** |
| Q18 | Admin moderation and account-suspension permissions? | Admin RBAC, effects of suspending a vendor with future bookings. | Stage 8 | Soon |

---

## D. Additional decisions found during analysis

| ID | Question | Why it matters | Needed before | Priority |
|---|---|---|---|---|
| N1 | Launch geography, currency and tax jurisdiction (boards imply Bengaluru, INR, GST). Time zone handling for venues. | Sets currency, tax rules, payment methods, hosting region and the time zone used to generate slots. | Stage 3 | **Blocker** |
| N2 | Slot granularity: fixed one-hour slots (as shown), owner-configurable duration (brief S7 "slot duration"), or both? Can a customer book several consecutive slots in one booking? | Defines how slots are generated, priced and stored; changes the booking schema and slot screen. | Stage 3 | **Blocker** |
| N3 | If a venue has several identical courts and the customer does not pick one, are courts auto-assigned? By what rule? | Without a rule the system cannot choose a court for the customer, or a court-selection step the boards do not show must be added. | Stage 6 | Soon |
| N4 | Temporary slot hold during payment: duration and behaviour on expiry (brief: do not invent). | Too short loses paying customers; too long blocks slots from others. The brief forbids inventing it. | Stage 6 | **Blocker** |
| N5 | Late payment after hold expiry: auto-refund, or honour if slot still free? | Decides whether a customer who pays late loses money or gets a slot they no longer hold; drives refund automation. | Stage 7 | Soon |
| N6 | Booking window: minimum notice and maximum advance days. Owner-side blackout rules. | Controls last-minute and far-future bookings; affects slot generation and owner control. | Stage 6 | Soon |
| N7 | Coupons/discounts (brief: "if approved"): who creates them (admin/owner), who funds them, limits, stacking. | Changes the pricing engine, who funds discounts and how abuse is prevented; the brief says only "if approved". | Stage 6 | Later |
| N8 | Owner dashboard definitions: utilisation formula (booked hours ÷ available hours?), "popular time slots", "average rating" scope, revenue basis (gross/net, booked vs completed). | Different formulas give different numbers; owners will compare them with their own records, so they must be agreed. | Stage 8 | Soon |
| N9 | Should owners see customer phone/email? (Brief: "where permitted"; O-S9 shows both.) Privacy basis and masking rules. | Customer contact data carries privacy exposure; owners may still need it to run the booking. | Stage 5 | Soon |
| N10 | Account identity rules: same person using Google and phone — merge or separate accounts? Is a phone number mandatory for customers? Phone OTP provider and (India) SMS sender registration requirements. | Wrong choices create duplicate accounts, lost booking history and unexpected SMS cost; shapes the auth design. | Stage 3 | **Blocker** |
| N11 | Owner onboarding verification: KYC, GST, business documents, bank verification before payouts. | Legal and payout compliance and fraud prevention depend on it; decides the owner onboarding screens. | Stage 5 | Soon |
| N12 | Admin authentication: separate credentials, 2FA, admin role tiers, admin audit logging requirements. | Admin accounts hold the most powerful access and are the weakest link if left unprotected. | Stage 3 | Soon |
| N13 | Who maintains master data (categories, amenities, cities)? Admin UI not in brief scope (C11). | Both apps depend on categories and amenities, and nobody is currently assigned to maintain them. | Stage 8 | Soon |
| N14 | Owner replies to reviews: one reply per review? Editable? Review moderation/reporting? | Defines how reviews can be answered and how abuse is handled. | Stage 8 | Later |
| N15 | Add to Calendar: device-native (.ics / calendar API) acceptable? | Affects time-zone correctness and device permissions; minor. | Stage 7 | Later |
| N16 | Languages and accessibility standard targets (WCAG level). | Affects text handling on every screen and the testing effort. | Stage 4 | Later |
| N17 | Data protection and retention: applicable law (e.g. India's DPDP Act), deletion requests, retention of financial records. Legal review required. | Legal compliance, deletion obligations, store requirements and retention of financial records. | Stage 3 | Soon |
| N18 | Non-functional targets: expected users, bookings per day, peak load, uptime, hosting region and budget. | Sizes infrastructure and plan tiers and defines pass or fail for load testing. | Stage 2 | Soon |
| N19 | Store accounts and publishing: Apple/Google developer accounts, bundle IDs, who owns them. Apple requires Sign in with Apple when other third-party sign-in is offered (already planned). | Apple and Google approvals take time; bundle IDs and signing are hard to change later. | Stage 2 | Soon |
| N20 | Support/Help: in-app help content, contact channel, ticketing; Terms, Privacy Policy and refund policy documents (referenced by login screens). | Stores require a privacy policy and terms; the login screens already link to them. | Stage 4 | Soon |
| N21 | Offline behaviour and minimum OS versions for mobile apps. | Determines supported devices and what can be cached. | Stage 4 | Later |
| N22 | Owner-initiated cancellations: allowed? Penalty to owner? Automatic full refund? (C10) | The Owner board has a Cancel Booking button; refunds, penalties and customer protection depend on the rule. | Stage 6 | **Blocker** |
| N23 | Do bookings of "gym" or "yoga" (class/time-pass style) behave like court slots or capacity-based sessions (multiple people per slot)? Boards only show court-style slots. | The exclusion-constraint design fits exclusive resources only; class-style bookings need a different mechanism. | Stage 3 | **Blocker** |

---

## E. Unconfirmed integrations

| Integration | Status | Recommendation (not decided) |
|---|---|---|
| Payment gateway + payouts | Not chosen (Q5, Q10) | Shortlist providers that support UPI, cards, net banking, signed webhooks and marketplace payouts/splits. |
| Maps / geocoding | Not chosen (Q13) | Pick after Q12. |
| Push notifications | Not chosen (Q14) | FCM + APNs via a single abstraction. |
| Email / SMS / WhatsApp | Not chosen (Q14) | Provider abstraction; decide channels first. |
| Image storage / CDN | Not chosen | S3-compatible object storage with signed uploads. |
| Social sign-in | Google, Apple shown | Confirm developer accounts (N19). |
| Analytics/crash reporting | Not mentioned | Optional; confirm. |

---

## F. Items to be confirmed with the client before implementation starts

Minimum answers to unblock Stages 2–3: **S1–S3, Q1, Q2, Q3, Q5, Q11, Q17, N1, N2, N10, N23**.
Minimum answers to unblock the booking engine (Stages 6–7): **Q7, Q8, Q9, Q16, N4, N22**.

---

## G. Updates after stack approval (Stage 2 review)

### G.1 Questions resolved or narrowed by the approved stack

| ID | Status | Effect |
|---|---|---|
| Q3 | **Resolved** | Two separate Flutter apps (Customer, Owner) in one monorepo, per the approved project structure. |
| Q13 | **Resolved** | Google Maps and Places. Remaining part: billing account and key restrictions (see N27). |
| Q5 | **Narrowed** | Razorpay approved, **pending confirmation of launch country and payment requirements** (see N25). |
| Q14 | **Partly resolved** | Push (FCM) and email (Resend) approved. SMS and WhatsApp are **not** approved. |
| C13/Q6 | Open | Wallet still depends on Razorpay account/method support. |

### G.2 New items introduced by the approved stack

| ID | Question | Why it matters | Needed before | Priority |
|---|---|---|---|---|
| N24 | Phone sign-in is shown on both boards, but Supabase phone OTP needs an SMS provider that is **not in the approved stack**. Which provider, or is phone login dropped or deferred? India sender/template registration requirements need checking. | Auth design, cost, long registration lead time | Stage 3 (start in Stage 1) | **Blocker** |
| N25 | Launch country and payment requirements for Razorpay (currency, supported methods, marketplace/split settlement, owner KYC). | Gateway suitability, payout design, tax | Stage 2 spike S2-4 | **Blocker** |
| N26 | Error tracking and crash reporting: Firebase Crashlytics and/or Sentry were not in the approved stack. Approve one, or accept logs only. | Production visibility | Stages 9–10 (decide by Stage 2) | Soon |
| N27 | Google Maps Platform billing account, expected usage and budget; who owns the Google Cloud project. | Keys and cost | Stage 4 | Soon |
| N28 | Supabase plan and region, Railway region, backup and point-in-time recovery expectations, and who owns each account. | Latency, data residency, recovery | Stage 2 | Soon |
| N29 | Mobile release automation: GitHub Actions builds only, or add a release tool (for example fastlane). | Release process | Stages 9–10 | Later |
| N30 | Domain names and email sender domain (admin site, API, Resend, Supabase SMTP). | Email deliverability, CORS, deep links | Stage 2 | Soon |
| N31 | Whether one person may hold both a customer and an owner account (architecture assumes one role per account). | Auth and schema | Stage 3 | Soon (extends N10) |
