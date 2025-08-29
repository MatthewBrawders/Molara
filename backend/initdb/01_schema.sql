-- database/initdb/01_schema.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS textbook_chunks (
  id         BIGSERIAL PRIMARY KEY,
  book_title TEXT NOT NULL,
  section    TEXT,
  chunk_idx  INT  NOT NULL,
  body       TEXT NOT NULL,
  embedding  VECTOR(384)  -- matches HF model
);

CREATE INDEX IF NOT EXISTS idx_textbook_title   ON textbook_chunks (book_title);
CREATE INDEX IF NOT EXISTS idx_textbook_section ON textbook_chunks (section);

CREATE INDEX IF NOT EXISTS idx_textbook_embed_cos
ON textbook_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 200);

ANALYZE textbook_chunks;
