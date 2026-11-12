# Environment files

Copy `dev.example.json` to `dev.json` (git-ignored) and fill in your **public** values:

- `SUPABASE_URL`, `SUPABASE_ANON_KEY`: from your Supabase project (anon key only; never the service-role key).
- `API_BASE_URL`: the backend, e.g. `http://localhost:8008/api/v1`.
  On the **Android emulator** use `http://10.0.2.2:8008/api/v1`; on a **physical device** use your computer's LAN IP.

Run: `flutter run --dart-define-from-file=env/dev.json`

Location is optional and never requested at launch. Google Maps/Places is **not** wired yet (see `docs/STEP_4_REPORT.md`); no Google key belongs in `dev.json`.
