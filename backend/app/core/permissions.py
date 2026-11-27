"""The admin permission registry. Roles are rows in `admin_roles`; they can only hold names listed here.

`super_admin` (the built-in system role) always resolves to EVERY permission defined here, so a
permission added later never silently goes missing for it. A newly created admin account has no
role at all and therefore no access until a `roles.manage` admin assigns one.
"""

SUPER_ADMIN = "super_admin"

PERMISSIONS: dict[str, str] = {
    "dashboard.view": "View the dashboard and activity feed",
    "analytics.view": "View analytics",
    "customers.view": "View customers",
    "customers.manage": "Suspend or reinstate customers",
    "owners.view": "View owners",
    "owners.manage": "Suspend or reinstate owners",
    "kyc.review": "View and review owner KYC documents",
    "venues.view": "View venues and venue reports",
    "venues.moderate": "Approve, reject, verify, suspend venues; handle reports",
    "bookings.view": "View bookings",
    "bookings.manage": "Cancel bookings in exceptional cases",
    "disputes.manage": "Manage booking disputes",
    "payments.view": "View payments, refunds and gateway events",
    "refunds.manage": "Initiate refunds and reconcile them",
    "finance.view": "View finance configuration, ledger, payouts and reports",
    "finance.manage": "Create finance configuration drafts and run reconciliation",
    "finance.approve": "Approve finance configurations (fees, tax, commission)",
    "commission.view": "View commission rules, history and commission reports",
    "commission.manage": "Create, change, activate and deactivate commission rules",
    "payouts.manage": "Create, approve and record owner payouts",
    "support.manage": "Handle support tickets",
    "categories.manage": "Manage sports categories",
    "coupons.manage": "Manage coupons",
    "cms.manage": "Manage CMS content",
    "roles.manage": "Manage admin roles and assignments",
    "settings.manage": "Change platform switches (approval workflow, refunds, payouts)",
    "audit.view": "View the audit log",
    "monitoring.view": "View system monitoring",
    "exports.download": "Download CSV reports",
}
ALL_PERMISSIONS = frozenset(PERMISSIONS)

# Permissions that move money or are otherwise irreversible: shown with a warning in the role editor.
SENSITIVE = frozenset(
    {
        "refunds.manage",
        "finance.approve",
        "commission.manage",
        "payouts.manage",
        "bookings.manage",
        "settings.manage",
        "roles.manage",
    }
)
