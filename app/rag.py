"""
rag.py — skill retrieval using bge-m3 embeddings.

Flow per request:
  1. At startup: embed all skills (name + description) → skill index
  2. Per file: embed content chunks + tags separately
  3. Fuse scores with RRF (Reciprocal Rank Fusion)
  4. Return top K skill dicts as candidate pool
  5. Prompt uses only this pool instead of all 136 skills

This narrows the LLM's choice from 136 → 15 skills,
which significantly improves skill mapping accuracy for small models.
"""
from __future__ import annotations
import re, torch
import pandas as pd
from config import (
    SKILLS_CSV_PATH, RAG_EMBED_MODEL_ID, RAG_POOL_K,
    RAG_CHUNK_CHARS, RAG_CHUNK_OVERLAP,
    RAG_TAG_WEIGHT, RAG_CONTENT_WEIGHT, RAG_RRF_K,
)

_embedder  = None
_skill_emb = None   # shape: [n_skills, dim]
_taxonomy  = []


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(RAG_EMBED_MODEL_ID, device="cpu")
    return _embedder


def _embed(texts):
    emb = _get_embedder()
    return emb.encode(
        list(texts), convert_to_tensor=True,
        normalize_embeddings=True, batch_size=32,
        show_progress_bar=False
    ).float()


def load_rag_index():
    """Call once at startup to build skill embeddings."""
    global _skill_emb, _taxonomy
    df = pd.read_csv(SKILLS_CSV_PATH)
    df["skill_name"] = df["skill_name"].astype(str).str.strip()
    df = df.drop_duplicates(subset=["skill_name"]).reset_index(drop=True)
    _taxonomy = [
        {"name": r.skill_name, "description": str(r.description).strip()}
        for r in df.itertuples(index=False)
    ]
    texts = [f"{s['name']}. {s['description'][:200]}" for s in _taxonomy]
    _skill_emb = _embed(texts)
    print(f"[RAG] index built: {len(_taxonomy)} skills embedded")


def _chunk(text, size=RAG_CHUNK_CHARS, overlap=RAG_CHUNK_OVERLAP):
    text = text.strip()
    if not text: return []
    step = max(1, size - overlap)
    chunks = [text[i:i+size] for i in range(0, len(text), step)]
    return [c for c in chunks if len(c.strip()) > 40] or [text[:size]]


def _rrf(scores):
    ranks = torch.argsort(torch.argsort(-scores))
    return 1.0 / (RAG_RRF_K + ranks.float() + 1.0)


def retrieve_skills(content_text: str, tags: list,
                    summary: str = "", k: int = RAG_POOL_K) -> list[dict]:
    """
    Returns top-k skill dicts [{"name": ..., "description": ...}]
    ranked by relevance to the content and tags.
    """
    if _skill_emb is None:
        load_rag_index()

    # content score — average over chunks
    chunks = _chunk(content_text)
    if chunks:
        chunk_emb      = _embed(chunks)
        content_sim    = chunk_emb @ _skill_emb.T
        content_scores = content_sim.topk(
            min(3, len(chunks)), dim=0).values.mean(0)
    else:
        content_scores = torch.zeros(len(_taxonomy),
                                     device=_skill_emb.device)

    # tag score
    tag_texts = [t for t in tags if str(t).strip()]
    if tag_texts:
        joined     = (summary + " Topics: " + "; ".join(tag_texts)).strip()
        tag_emb    = _embed([joined] + tag_texts)
        tag_scores = (0.5 * (tag_emb[0] @ _skill_emb.T)
                      + 0.5 * (tag_emb[1:] @ _skill_emb.T).mean(0))
    else:
        tag_scores = torch.zeros(len(_taxonomy),
                                 device=_skill_emb.device)

    # RRF fusion
    fused = (RAG_CONTENT_WEIGHT * _rrf(content_scores)
             + RAG_TAG_WEIGHT   * _rrf(tag_scores))

    top_idx = fused.topk(k=min(k, len(_taxonomy))).indices.tolist()
    return [_taxonomy[i] for i in top_idx]


def retrieval_recall(gold_skills: list, pool: list[dict]) -> float | None:
    """
    Fraction of gold skills found in the retrieved pool.
    Used as the 'retrieval_quality' metric when RAG is enabled.
    """
    if not gold_skills or not pool:
        return None
    pool_names = {re.sub(r"[^a-z0-9]+", " ", s["name"].lower()).strip()
                  for s in pool}
    gold_norm  = {re.sub(r"[^a-z0-9]+", " ", g.lower()).strip()
                  for g in gold_skills if str(g).strip()}
    if not gold_norm:
        return None
    return round(len(gold_norm & pool_names) / len(gold_norm), 3)
