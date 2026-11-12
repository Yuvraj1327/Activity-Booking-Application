# Environment configuration (customer app)

Config is a standard `.env` file loaded at startup with `flutter_dotenv` (bundled as an asset). It is git-ignored; `.env.example` is the tracked template.

```
cp .env.example .env     # then fill in your public values
flutter run
```

- `SUPABASE_URL`, `SUPABASE_ANON_KEY`: from your Supabase project (anon key only; never the service-role key).
- `API_BASE_URL`: the backend, e.g. `http://localhost:8008/api/v1`.
  On the **Android emulator** use `http://10.0.2.2:8008/api/v1`; on a **physical device** use your computer's LAN IP.
- `AUTH_REDIRECT_URL`: `io.zuruv.customer://login-callback` (allow-list it in Supabase).
- `GOOGLE_AUTH_ENABLED`, `APPLE_AUTH_ENABLED`, `PHONE_AUTH_ENABLED`: `true`/`false`.

The `.env` is shipped inside the app bundle, so it holds **public values only**: never a service-role key, payment secret or other backend secret.

Location is optional and never requested at launch. Maps/Places goes through the backend (`GOOGLE_MAPS_API_KEY` is a server variable); no Google key belongs in `.env`.
