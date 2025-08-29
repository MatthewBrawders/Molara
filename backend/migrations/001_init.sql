-- Enable pgvector and text search
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- optional but handy

-- Main storage for RAG
CREATE TABLE IF NOT EXISTS textbook_chunks (
  id         BIGSERIAL PRIMARY KEY,
  book_title TEXT NOT NULL,
  section    TEXT NOT NULL DEFAULT 'Full Text',
  chunk_idx  INT  NOT NULL,
  body       TEXT NOT NULL,
  embedding  vector(384),                -- matches EMBEDDING_DIM default
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unique position per (book, section)
CREATE UNIQUE INDEX IF NOT EXISTS uq_textbook_chunks_book_sec_idx
  ON textbook_chunks (book_title, section, chunk_idx);

-- Full-text support (optional but useful alongside vector search)
ALTER TABLE textbook_chunks
  ADD COLUMN IF NOT EXISTS body_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(body,''))) STORED;

CREATE INDEX IF NOT EXISTS idx_textbook_chunks_tsv
  ON textbook_chunks USING GIN (body_tsv);

-- Vector index for ANN (safe if column is NULL initially)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public' AND indexname = 'idx_textbook_chunks_embedding'
  ) THEN
    CREATE INDEX idx_textbook_chunks_embedding
      ON textbook_chunks
      USING ivfflat (embedding vector_l2_ops)
      WITH (lists = 100);
  END IF;
END$$;

-- Helpful view for debugging searches
CREATE OR REPLACE VIEW textbook_chunks_overview AS
SELECT id, book_title, section, chunk_idx,
       left(body, 160) || CASE WHEN length(body) > 160 THEN '…' ELSE '' END AS body_preview,
       created_at,
       (embedding IS NOT NULL) AS has_embedding
FROM textbook_chunks;
