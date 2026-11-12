import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg


@asynccontextmanager
async def session_as(
    url: str,
    uid: uuid.UUID | None = None,
    *,
    role: str = "authenticated",
    force_write_grants: bool = False,
) -> AsyncIterator[asyncpg.Connection]:
    """A transaction running as a Supabase API role, with request.jwt.claims set like PostgREST
    does. Always rolled back. `force_write_grants` temporarily GRANTs INSERT/UPDATE/DELETE so a
    test can prove that RLS alone (not just missing grants) blocks writes."""
    conn = await asyncpg.connect(url)
    tx = conn.transaction()
    await tx.start()
    try:
        if force_write_grants:
            await conn.execute(
                "GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO anon, authenticated"
            )
        await conn.execute(f"SET LOCAL ROLE {role}")
        if uid is not None:
            claims = json.dumps({"sub": str(uid), "role": role})
            await conn.execute(
                "SELECT set_config('request.jwt.claims', $1, true), set_config('request.jwt.claim.sub', $2, true)",
                claims,
                str(uid),
            )
        yield conn
    finally:
        await tx.rollback()
        await conn.close()
