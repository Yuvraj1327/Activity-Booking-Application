# Admin permission matrix

> **Superseded in part by [ADMIN_OPERATIONS.md](ADMIN_OPERATIONS.md).** Administration is now permission based:
> an admin needs a role (`admin_roles` / `admin_profiles`) and every route checks a named permission. The table
> below describes the original single-tier behaviour, which `super_admin` (the migrated role of every existing
> admin) still has. New write actions (refunds, cancellation, venue moderation, payouts, ...) each have their own permission.

# Admin permission matrix (Step 8, original)

Only the backend decides. "Admin" means a `profiles.role = 'admin'`, active, MFA-verified when `ADMIN_REQUIRE_MFA` is on.

| Capability | Anonymous | Customer | Owner | Suspended admin | Admin |
|---|---|---|---|---|---|
| Any `/admin/*` route | 401 | 403 | 403 | 403 `ACCOUNT_SUSPENDED` | ✔ |
| View dashboard, analytics, activity | ✖ | ✖ | ✖ | ✖ | ✔ |
| List/view owners, customers | ✖ | ✖ | ✖ | ✖ | ✔ (contact masked in lists) |
| Suspend / reactivate owner or customer | ✖ | ✖ | ✖ | ✖ | ✔ audited, reason required |
| Suspend / change an admin, or self | ✖ | ✖ | ✖ | ✖ | ✖ (refused) |
| View venues | ✖ | ✖ | ✖ | ✖ | ✔ read-only |
| Edit, publish, delete a venue or court | ✖ | ✖ | own only | ✖ | **✖** (not authorised) |
| View bookings, payments | ✖ | ✖ | ✖ | ✖ | ✔ read-only |
| Change a booking or payment status | ✖ | ✖ | ✖ | ✖ | **✖** (state machine only) |
| Export CSV | ✖ | ✖ | ✖ | ✖ | ✔ audited, capped, no contact data |
| Read audit log | ✖ | ✖ | ✖ | ✖ | ✔ |
| Become admin through the API | ✖ | ✖ | ✖ | ✖ | ✖ (operator script only) |

## Pending decision

Q18 (moderation and suspension powers, and what suspension does to future bookings) is **open**. The current implementation is the conservative default: suspend and reactivate only, nothing automatic happens to bookings, no admin edits to vendor listings. A broader admin role-based model (N12) is not built.

## Commission management permissions

Added with migration `0012`. `super_admin` has both automatically; custom roles must be granted them.

| Permission | Allows |
|---|---|
| `commission.view` | Read commission rules, history, the calculation preview. Shows the Commission menu. |
| `commission.manage` | Create rules; change, activate, deactivate (sensitive: shown with a warning in the role editor). |
| `finance.view` (existing) | Commission reports, booking commission details, owner earnings view. |
| `exports.download` + `finance.view` | `commission.csv` export. |

Customers and owners cannot reach any `/admin/commission/*` route (403). Owners can read only their own venues' rates and earnings under `/owners/commission` and `/owners/earnings/*`. See [COMMISSION_MANAGEMENT.md](COMMISSION_MANAGEMENT.md).
