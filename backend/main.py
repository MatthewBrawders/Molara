from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import httpx
import json
import time
import asyncio

import db
from embeddings import embed_texts

EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434").rstrip("/")
# Keep this consistent with your docker-compose GEN_MODEL
GEN_MODEL  = os.environ.get("GEN_MODEL", "qwen2.5:3b")

app = FastAPI(title="Textbook RAG API")

# --- CORS (adjust origins as needed) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://your-frontend.example"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Models --------------------

class ChunkIn(BaseModel):
    book_title: str
    section: Optional[str] = None
    chunk_idx: int = 0
    body: str

class InsertWithEmbeddingIn(BaseModel):
    book_title: str
    section: Optional[str] = None
    chunk_idx: int = 0
    body: str
    embedding: List[float]

class SearchIn(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=50)

class QueryIn(BaseModel):
    question: str
    top_k: int = Field(5, ge=1, le=50)

class ChunkOut(BaseModel):
    id: Optional[int] = None
    book_title: str
    section: str
    chunk_idx: int
    body: str
    score: Optional[float] = None  # distance (lower = closer)

class QueryOut(BaseModel):
    answer: str
    sources: List[ChunkOut]

# -------------------- Lifecycle --------------------

@app.on_event("startup")
async def _startup():
    await db.init()
    # Light, non-blocking warmup for Ollama; ignore failures
    try:
        _ = await ollama_generate("hi", model=GEN_MODEL)
    except Exception:
        pass

@app.on_event("shutdown")
async def _shutdown():
    await db.close()

# -------------------- Health --------------------

@app.get("/health")
async def health():
    return {"ok": True}

# -------------------- Ingest --------------------

@app.post("/chunks/auto")
async def add_chunk_auto(c: ChunkIn):
    """Embed and insert a single chunk."""
    section = c.section or "Full Text"
    vec = (await embed_texts([c.body]))[0]
    if len(vec) != EMBEDDING_DIM:
        raise HTTPException(500, f"Embedding dim mismatch: got {len(vec)} expected {EMBEDDING_DIM}")

    async with db.conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO textbook_chunks (book_title, section, chunk_idx, body, embedding)
                VALUES (%s, %s, %s, %s, %s::vector)
                """,
                (c.book_title, section, c.chunk_idx, c.body, vec),
            )
    return {"status": "inserted"}

@app.post("/chunks/raw")
async def add_chunk_raw(c: InsertWithEmbeddingIn):
    """Insert when embedding is precomputed client-side."""
    section = c.section or "Full Text"
    if len(c.embedding) != EMBEDDING_DIM:
        raise HTTPException(400, f"Embedding dim must be {EMBEDDING_DIM}")

    async with db.conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO textbook_chunks (book_title, section, chunk_idx, body, embedding)
                VALUES (%s, %s, %s, %s, %s::vector)
                """,
                (c.book_title, section, c.chunk_idx, c.body, c.embedding),
            )
    return {"status": "inserted"}

# -------------------- Retrieval --------------------

@app.post("/search", response_model=List[ChunkOut])
async def semantic_search(q: SearchIn):
    """
    Vector search (L2 distance by default with '<->').
    Returns rows ordered by distance ASC; lower = more similar.
    """
    vec = (await embed_texts([q.query]))[0]
    if len(vec) != EMBEDDING_DIM:
        raise HTTPException(500, f"Embedding dim mismatch: got {len(vec)} expected {EMBEDDING_DIM}")

    async with db.conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, book_title, COALESCE(section, 'Full Text') AS section,
                       chunk_idx, body,
                       (embedding <-> %s::vector) AS dist
                FROM textbook_chunks
                ORDER BY dist ASC
                LIMIT %s
                """,
                (vec, q.top_k),
            )
            rows = await cur.fetchall()

    return [
        ChunkOut(
            id=r[0],
            book_title=r[1],
            section=r[2],
            chunk_idx=r[3],
            body=r[4],
            score=float(r[5]) if r[5] is not None else None
        )
        for r in rows
    ]

# -------------------- Full RAG (with Ollama) --------------------

def build_prompt(question: str, chunks: List[ChunkOut]) -> str:
    context = "\n\n".join(
        f"[{i+1}] (book={c.book_title}, section={c.section}, idx={c.chunk_idx})\n{c.body}"
        for i, c in enumerate(chunks)
    )
    # Tight, grounded instruction:
    return (
        "You are a precise scientific assistant. Use ONLY the context to answer.\n"
        "Cite sources with [1], [2], etc., matching the bracketed chunks.\n"
        "If the answer is not contained in the context, say you don't know.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

async def ollama_generate(prompt: str, model: str = GEN_MODEL) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_ctx": 8192
        }
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or "").strip()

@app.post("/query/stream")
async def query_stream(q: QueryIn):
    """
    Streams an answer token-by-token using Ollama's stream API and
    re-emits it as SSE-like events: each event is `data: {...}\n\n`.
    The frontend reads it via fetch ReadableStream (no EventSource so POST works).
    """
    # 1) retrieve top-k chunks (reuse your existing search)
    top_chunks = await semantic_search(SearchIn(query=q.question, top_k=q.top_k))
    if not top_chunks:
        async def empty_stream():
            yield "data: " + json.dumps({"delta": "", "final": True, "sources": []}) + "\n\n"
        return StreamingResponse(
            empty_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    prompt = build_prompt(q.question, top_chunks)

    async def event_stream():
        payload = {
            "model": GEN_MODEL,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_ctx": 8192
            }
        }

        heartbeat_every = 15.0  # seconds
        last_heartbeat = time.monotonic()

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/generate", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    # Heartbeat to keep proxies from closing idle streams
                    now = time.monotonic()
                    if now - last_heartbeat >= heartbeat_every:
                        # SSE comment event (ignored by clients, keeps connection open)
                        yield ": ping\n\n"
                        last_heartbeat = now

                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if "response" in obj and obj["response"]:
                        # stream incremental delta
                        yield "data: " + json.dumps({"delta": obj["response"]}) + "\n\n"
                    if obj.get("done"):
                        break

        # final event with sources (for citations list)
        sources_payload = [
            {
                "id": s.id,
                "book_title": s.book_title,
                "section": s.section,
                "chunk_idx": s.chunk_idx,
                "score": s.score,
            }
            for s in top_chunks
        ]
        yield "data: " + json.dumps({"final": True, "sources": sources_payload}) + "\n\n"
        # small delay to ensure client reads the final event before close (optional)
        await asyncio.sleep(0)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # helps Nginx not buffer SSE
        },
    )
