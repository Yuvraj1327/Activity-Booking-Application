# ZURUV — Discover. Book. Play.

Sports, fitness and leisure venue booking platform: **one Flutter mobile app** (customers and venue owners sign in once and each lands on their own dashboard), a separate **Admin web** console (Next.js), one **FastAPI** backend and one **Supabase** project (PostgreSQL, Auth, Storage).

> Status: **Step 3 — authentication and database foundation** is implemented (see [docs/STEP_3_REPORT.md](docs/STEP_3_REPORT.md) for what is and is not verified). Venue, booking and payment features are not built yet.

## Layout

| Path | What |
|---|---|
| `apps/mobile_app` | The one Flutter app (ZURUV): Customer and Venue Owner roles, one APK / one AAB. See [docs/MOBILE_APP.md](docs/MOBILE_APP.md) |
| `apps/admin_web` | Next.js admin console |
| `packages/flutter_shared` | Shared Flutter code (theme, config, API client, common widgets) |
| `backend` | FastAPI service (port **8008**), SQLAlchemy 2 async, Alembic |
| `supabase` | Supabase local config and RLS migration directory |
| `docs` | Architecture, roadmap, setup guides |

Details: [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md).

## Quick start

Full instructions: [docs/DEVELOPMENT_SETUP.md](docs/DEVELOPMENT_SETUP.md). Variables: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md).

```bash
# Backend (from repo root)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # then fill in YOUR Supabase values
uvicorn app.main:app --reload --host 0.0.0.0 --port 8008
# http://localhost:8008/health   http://localhost:8008/docs

# Admin web
cd apps/admin_web && cp .env.example .env.local && npm install && npm run dev   # http://localhost:3000

# Mobile app (needs Flutter >= 3.27)
./scripts/bootstrap_flutter.sh
cd apps/mobile_app && cp .env.example .env && flutter run
```

`make help` lists the shortcut targets.

## Rules

- Secrets live only in git-ignored `.env` files. The Supabase service-role key exists only on the backend.
- Clients use Supabase for sign-in only; all data goes through the FastAPI API. The mobile app and the admin website use the same API and database.
- Admins use the website only; the mobile app signs admin accounts out.
- Schema changes go through Alembic only (`backend/alembic`). Roles come from the database, never from the client or the token.
- Docs: [Database](docs/DATABASE_SCHEMA.md) · [Authentication](docs/AUTHENTICATION_FLOW.md) · [Permissions](docs/ROLE_PERMISSION_MATRIX.md) · [Storage](docs/STORAGE_CONFIGURATION.md) · [API](docs/API_DOCUMENTATION.md)
