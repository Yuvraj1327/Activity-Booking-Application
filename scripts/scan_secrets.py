#!/usr/bin/env python3
"""Fail if anything that looks like a real secret is in the repo or in a built web bundle.

Usage: python scripts/scan_secrets.py [extra_dir ...]   (e.g. apps/admin_web/.next/static)
Scans the repo (skipping dependency/build folders) plus any extra directories given.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "node_modules", ".venv", ".next", ".dart_tool", "pgdata", "__pycache__", ".mypy_cache",
             ".ruff_cache", ".pytest_cache", "test-results", ".stack", "report", "build", "playwright-report"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".zip", ".woff", ".woff2", ".lock", ".pyc"}
PATTERNS = {
    "Razorpay live key": re.compile(r"rzp_live_[A-Za-z0-9]{10,}"),
    "Razorpay key secret-like": re.compile(r"""key_secret["']?\s*[:=]\s*["'][A-Za-z0-9]{20,}["']"""),
    "Private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "Resend key": re.compile(r"\bre_[A-Za-z0-9]{24,}\b"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "Stripe-style live key": re.compile(r"\bsk_live_[A-Za-z0-9]{10,}"),
    "JWT (hard-coded token)": re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"),
    "Firebase service account": re.compile(r'"type"\s*:\s*"service_account"'),
}
# Names that must never be read by client code.
CLIENT_FORBIDDEN = re.compile(r"SUPABASE_SERVICE_ROLE|SERVICE_ROLE_KEY|RAZORPAY_KEY_SECRET|RAZORPAY_WEBHOOK_SECRET")
CLIENT_DIRS = ("apps/admin_web/src", "apps/mobile_app/lib", "packages/flutter_shared/lib")


def files(base: Path):
    for p in base.rglob("*"):
        if p.is_file() and not (set(p.relative_to(base).parts[:-1]) & SKIP_DIRS) and p.suffix not in SKIP_SUFFIX:
            yield p


def main() -> int:
    problems: list[str] = []
    targets = [ROOT] + [Path(a).resolve() for a in sys.argv[1:]]
    for base in targets:
        iterator = files(base) if base == ROOT else (p for p in base.rglob("*") if p.is_file())
        for p in iterator:
            if p.name.endswith(".example") or ".example." in p.name:
                continue
            try:
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            for name, rx in PATTERNS.items():
                if rx.search(text) and "tests/" not in str(p) and "/test/" not in str(p):
                    problems.append(f"{name}: {p.relative_to(ROOT) if ROOT in p.parents else p}")
            rel = str(p.relative_to(ROOT)) if ROOT in p.parents else ""
            if (rel.startswith(CLIENT_DIRS) or base != ROOT) and CLIENT_FORBIDDEN.search(text):
                problems.append(f"server-only secret name in client code: {rel or p}")
    if problems:
        print("SECRET SCAN FAILED")
        print("\n".join(sorted(set(problems))))
        return 1
    print(f"secret scan clean ({len(targets)} target(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
