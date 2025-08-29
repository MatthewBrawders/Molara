from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import os

import db
from embeddings import embed_texts

EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "384"))

app = FastAPI(title="Textbook RAG API (HF)")

class ChunkIn(BaseModel):
    book_title: str
    section: Optional[str] = None
    chunk_idx: int = 0
    body: str

class SearchIn(BaseModel):
    query: str
    top_k: int = Field(5, ge=1, le=50)

class InsertWithEmbeddingIn(BaseModel):
    book_title: str
    section: Optional[str] = None
    chunk_idx: int = 0
    body: str
    embedding: List[float]  

@app.on_event("startup")
async def _startup():
    await db.init()

@app.on_event("shutdown")
async def _shutdown():
    await db.close()

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/chunks/auto")
async def add_chunk_auto(c: ChunkIn):
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
                (c.book_title, c.section, c.chunk_idx, c.body, vec),
            )
    return {"status": "inserted"}

@app.post("/chunks/raw")
async def add_chunk_raw(c: InsertWithEmbeddingIn):
    if len(c.embedding) != EMBEDDING_DIM:
        raise HTTPException(400, f"Embedding dim must be {EMBEDDING_DIM}")
    async with db.conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO textbook_chunks (book_title, section, chunk_idx, body, embedding)
                VALUES (%s, %s, %s, %s, %s::vector)
                """,
                (c.book_title, c.section, c.chunk_idx, c.body, c.embedding),
            )
    return {"status": "inserted"}

@app.post("/search")
async def semantic_search(q: SearchIn):
    vec = (await embed_texts([q.query]))[0]
    if len(vec) != EMBEDDING_DIM:
        raise HTTPException(500, f"Embedding dim mismatch: got {len(vec)} expected {EMBEDDING_DIM}")
    async with db.conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, book_title, section, chunk_idx, body
                FROM textbook_chunks
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (vec, q.top_k),
            )
            rows = await cur.fetchall()
    return [
        {
            "id": r[0],
            "book_title": r[1],
            "section": r[2],
            "chunk_idx": r[3],
            "body": r[4],
        } for r in rows
    ]
