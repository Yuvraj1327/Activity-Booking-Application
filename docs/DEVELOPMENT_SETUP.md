# Development setup

Prerequisites: Python 3.13, Node 20.9+ (tested on 22), Flutter 3.27+ (Dart 3.6+), Git. Docker is optional.

## 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # fill in your Supabase values
uvicorn app.main:app --reload --host 0.0.0.0 --port 8008
```

Check: `curl localhost:8008/health` — without a database configured it returns `"status":"degraded"` and `"database":{"status":"not_configured"}` (that is correct). With a working `DATABASE_URL` it returns `"status":"ok"`. Swagger: <http://localhost:8008/docs>.

```bash
alembic upgrade head                 # applies the Step 3 schema to DATABASE_URL (a Supabase database)
python -m scripts.create_admin --email you@example.com --name "Your Name"   # after creating the user in Supabase
ruff check . && ruff format --check . && mypy
```

### Backend tests (need a throwaway PostgreSQL, never your Supabase project)

```bash
../scripts/dev_pg.sh start           # no Docker: temporary local PostgreSQL on port 54399 (prints the URL)
# or: docker compose up -d db        # then use postgresql://<user>:<password>@localhost:5432/<db>
export TEST_DATABASE_URL=postgresql://zt@127.0.0.1:54399/postgres   # must be a superuser
pytest                               # 151 tests; each session makes its own database, loads
                                     # supabase/local/supabase_stub.sql, runs alembic, then drops it
../scripts/dev_pg.sh stop
```
Without `TEST_DATABASE_URL`, the 115 database tests are **skipped** (reported as skipped, not passed).
`supabase/local/supabase_stub.sql` imitates only the Supabase parts the migrations need (roles, `auth.users`, `auth.uid()`, Storage tables). Use it on local databases only.

Supabase pooler: for the transaction pooler (port 6543) set `DB_USE_NULLPOOL=true`; run Alembic with `ALEMBIC_DATABASE_URL` pointing at the direct or session connection.

## 1b. Supabase project (required for real sign-in)

Follow the dashboard checklist in [AUTHENTICATION_FLOW.md](AUTHENTICATION_FLOW.md), then apply the schema once: `ALEMBIC_DATABASE_URL=<direct or session connection> alembic upgrade head`.

## 2. Admin web

```bash
cd apps/admin_web
cp .env.example .env.local
npm install
npm run dev                          # http://localhost:3000
npm run lint && npm run typecheck && npm run build
```

### Reference data and sample venues (development / staging only)

After `alembic upgrade head` (from `backend/`, with `DATABASE_URL` or `ALEMBIC_DATABASE_URL` set):

```bash
python -m scripts.seed_reference_data                      # categories, amenities, cities (any environment, idempotent)
python -m scripts.seed_demo_venues --owner-email you@x.com # 6 labelled "(Demo)" venues owned by an EXISTING owner account
python -m scripts.seed_demo_venues --remove                # delete them again
```

The demo script refuses to run when `ENVIRONMENT=production`, adds no images, ratings or reviews, and the apps never contain this data: they read everything from the API. Add real photos through the Owner app (Step 5) or Supabase Storage (`venue-images/<venue id>/<file>`, then a `venue_images` row).

## 3. Flutter apps

```bash
./scripts/bootstrap_flutter.sh       # creates android/ios runners, runs pub get (once)
cd apps/customer_app                 # or apps/owner_app
cp env/dev.example.json env/dev.json # fill in public values
flutter run --dart-define-from-file=env/dev.json
flutter analyze && flutter test
```

Customer app prerequisites: the backend running, `seed_reference_data` run, and your Supabase values in `env/dev.json`. On a fresh clone `bootstrap_flutter.sh` also runs `scripts/configure_customer_platforms.py`, which adds the location and photo permissions and the `io.zuruv.customer://login-callback` deep link to the generated Android/iOS runners.

```bash
cd ../../packages/flutter_shared && flutter test
```

## 4. Optional local Postgres

```bash
cp .env.example .env                 # set POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
docker compose up -d db
# DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<db>
```
This is plain PostGIS, not Supabase: it has no Auth or Storage.

## Git

Secrets are ignored (`.env*` except `.env.example`, `env/*.json` except `*.example.json`, keys, keystores, `google-services.json`). Check before committing: `git status` and `git diff --cached`.
