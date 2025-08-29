import os
from typing import List
from sentence_transformers import SentenceTransformer

MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_model = SentenceTransformer(MODEL_NAME)

def _ensure_listfloat(v) -> list[float]:
    return [float(x) for x in v]

async def embed_texts(texts: List[str]) -> List[List[float]]:
    vecs = _model.encode(texts, normalize_embeddings=True)
    return [ _ensure_listfloat(v) for v in vecs ]
