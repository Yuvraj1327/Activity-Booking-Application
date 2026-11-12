# Storage configuration

Created by Alembic revision `0003` (not by hand), so hosted projects and tests get identical buckets and policies.

| Bucket | Visibility | Max size | Allowed types | Who may write |
|---|---|---|---|---|
| `venue-images` | **public** (listing photos) | 5 MiB | jpeg, png, webp | **Backend only** (service role, Step 5). No client policy exists. |
| `profile-images` | **private** | 2 MiB | jpeg, png, webp | The signed-in user, only at `profile-images/<own user id>/<file>.jpg|jpeg|png|webp` |

> **Assumption to confirm:** the size limits and allowed types are my defaults. The architecture (§19) says they are configuration values "to be set", and no one has set them. Change them in `0003`/a new revision and `supabase/config.toml`.

## Policies on `storage.objects` (profile-images)

`SELECT`, `INSERT`, `UPDATE`, `DELETE` for `authenticated`, each requiring:
1. `bucket_id = 'profile-images'`
2. `name` matches `^<auth.uid()>/[A-Za-z0-9_-]{1,100}\.(jpg|jpeg|png|webp)$`: own folder, no nesting, no `..`, no other extensions
3. the caller's account is active

Consequences (all tested against the local stub): a user cannot read, overwrite, delete or move files into another user's folder; a suspended user cannot upload; `anon` has no access; `venue-images` cannot be written by any client.

## Reading files

- **Venue images** are public: store `venue_images.storage_path` and build the public URL `…/storage/v1/object/public/venue-images/<path>`.
- **Profile images** are private: the app asks Storage for a short-lived signed URL (`createSignedUrl`) with the user's own token, or the API signs one. Store only `profiles.avatar_path` (the API refuses paths outside the caller's folder; a DB CHECK enforces it too).

## What is and is not verified

- Verified (local PostgreSQL + stub): policy logic, per-user isolation, traversal and prefix tricks, suspended users, no client writes to `venue-images`.
- **Not verified:** that the real Supabase Storage service enforces `file_size_limit` / `allowed_mime_types`, that migrations may create policies on `storage.objects` with your project's database role, and signed-URL behaviour. Check on your project (Storage > Policies) after `alembic upgrade head`.
- Image re-encoding / EXIF stripping (architecture §19) belongs to the venue-image upload flow in Step 5.

## Security notes
- Never put the service-role key in Flutter or Next.js. Only the backend would use it, and nothing in Step 3 needs it.
- Object names are random; user filenames are never used as paths.
