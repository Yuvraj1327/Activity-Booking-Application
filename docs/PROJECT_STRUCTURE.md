# Project structure

```
zuruv/
├── apps/
│   ├── mobile_app/          The one Flutter app "ZURUV" (lib/main.dart, app.dart, core/, customer/, owner/)
│   └── admin_web/           Next.js (App Router, TypeScript, Tailwind v4, hand-written shadcn-style UI)
│       └── src/{app,components/{ui,layout},lib}
├── packages/
│   └── flutter_shared/      theme, AppEnv, Dio API client, Supabase bootstrap, ErrorView/LoadingView/responsive
├── backend/
│   ├── app/
│   │   ├── main.py          app factory + GET /health        (uvicorn app.main:app)
│   │   ├── api/             deps.py, v1/{router.py,endpoints/}
│   │   ├── core/            config, logging, errors, middleware, security (JWT)
│   │   ├── database/        async engine/session, health check
│   │   ├── models/          SQLAlchemy Base (no tables until Step 3)
│   │   ├── schemas/         Pydantic schemas
│   │   ├── services/        business logic (empty)
│   │   ├── repositories/    data access (empty)
│   │   └── utils/
│   ├── alembic/             env.py (async), versions/0001 tables, 0002 triggers, 0003 RLS+storage
│   ├── scripts/             create_admin.py (operator tool)
│   ├── tests/               pytest
│   ├── requirements.txt, requirements-dev.txt, pyproject.toml, alembic.ini, Dockerfile, .env.example
├── supabase/                config.toml, migrations/ (reserved), local/supabase_stub.sql (LOCAL TEST ONLY)
├── docs/                    Step 1 documents, Step 2 documents, reference/ (UI boards)
├── scripts/                 bootstrap_flutter.sh, configure_mobile_platforms.py, dev_pg.sh (throwaway local Postgres)
├── docker-compose.yml       optional local Postgres (+ API under profile "api")
├── Makefile, .gitignore, .env.example, README.md
└── .github/workflows/       CI (backend, admin)
```

## Differences from the paths written in Step 1

| Step 1 documents | Step 2 (actual) | Why |
|---|---|---|
| `/v1/...` | `/api/v1/...` | Step 2 brief |
| `/healthz`, `/readyz` | `GET /health` (status + DB state) | Step 2 brief |
| `services/api` | `backend/` | Step 2 brief |
| Alembic under `database/` | `backend/alembic` | Alembic belongs with the service that owns the models |
| several Flutter packages, Dart workspace | one `flutter_shared`, path dependencies | Simpler; split later if needed |
| `uv` | `requirements*.txt` + venv | Step 2 brief |
| `backend/main.py` (brief) | `backend/app/main.py` | The mandated run command is `uvicorn app.main:app` |

The architecture itself (modular monolith, Supabase for auth only, RLS with no client policies, Alembic-only migrations) is unchanged.
