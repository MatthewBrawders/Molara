import os
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@db:5432/textbook")
IVFFLAT_PROBES = int(os.environ.get("IVFFLAT_PROBES", "10"))

_pool: AsyncConnectionPool | None = None

async def init():
    global _pool
    _pool = AsyncConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=True)

async def close():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

@asynccontextmanager
async def conn():
    async with _pool.connection() as c:
        async with c.cursor() as cur:
            await cur.execute("SET ivfflat.probes = %s;", (IVFFLAT_PROBES,))
        yield c
