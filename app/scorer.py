"""
scorer.py — quality scoring and benchmark aggregation.

7 required metrics (project guide):
  1. Tagging/classification accuracy
  2. Skill-mapping accuracy
  3. Retrieval quality  (N/A without RAG, pool recall with RAG)
  4. Structured-output validity
  5. Latency
  6. Token usage / cost
  7. Scalability (items/hour)

Extra metrics added:
  8.  Tag semantic F1          — semantic tag match beyond strict overlap
  9.  Tag precision            — of predicted tags, how many were correct
  10. Tag recall               — of gold tags, how many were found
  11. Skill precision          — of predicted skills, how many were correct
  12. Tokens per second        — generation speed (GPU comparison)
  13. Cost per 1000 files      — business-level cost estimate
"""
from __future__ import annotations
import math, re
import torch
from config import (
    COMPUTE_SEMANTIC_METRICS, SCORING_EMBED_MODEL_ID, TAG_SIM_THRESHOLD,
    VALID_DIFFICULTY, GPU_COST_PER_HOUR_USD,
    OPENAI_INPUT_COST_PER_1K, OPENAI_OUTPUT_COST_PER_1K, N_OUTPUT_SKILLS,
)
from prompts import norm_skill

# ── embedder (lazy, loaded once) ──────────────────────────────────────────────
_embedder = None

def _get_embedder():
    global _embedder
    if _embedder is None and COMPUTE_SEMANTIC_METRICS:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(SCORING_EMBED_MODEL_ID, device="cpu")
    return _embedder

def _embed(texts):
    emb = _get_embedder()
    if emb is None or not texts: return None
    return emb.encode(list(texts), convert_to_tensor=True,
                      normalize_embeddings=True, batch_size=32,
                      show_progress_bar=False).float()

# ── helpers ───────────────────────────────────────────────────────────────────
def _norm(t): return re.sub(r"[^a-z0-9]+", " ", str(t).lower()).strip()

def split_multi(v):
    if v is None or (isinstance(v, float) and math.isnan(v)): return []
    return [x.strip() for x in re.split(r"\s*\|\s*|\s*;\s*", str(v)) if x.strip()]

def jaccard(a, b):
    a = {_norm(x) for x in a if str(x).strip()}
    b = {_norm(x) for x in b if str(x).strip()}
    if not a and not b: return None
    return round(len(a & b) / len(a | b), 3)

def precision(pred, gold):
    """Of what the model predicted, how many were correct."""
    pn = {_norm(x) for x in pred if str(x).strip()}
    gn = {_norm(x) for x in gold if str(x).strip()}
    if not pn: return None
    return round(len(pn & gn) / len(pn), 3)

def recall(pred, gold):
    """Of the gold set, how many did the model find."""
    pn = {_norm(x) for x in pred if str(x).strip()}
    gn = {_norm(x) for x in gold if str(x).strip()}
    if not gn: return None
    return round(len(pn & gn) / len(gn), 3)

def semantic_f1(pred, gold, thr=TAG_SIM_THRESHOLD):
    if not pred or not gold: return None, []
    emb_pred = _embed(pred)
    emb_gold = _embed(gold)
    if emb_pred is None or emb_gold is None: return None, []
    S = (emb_pred @ emb_gold.T).cpu()
    flat = sorted(((float(S[i, j]), i, j)
                   for i in range(len(pred))
                   for j in range(len(gold))), reverse=True)
    used_p, used_g, pairs = set(), set(), []
    for s, i, j in flat:
        if s < thr: break
        if i in used_p or j in used_g: continue
        used_p.add(i); used_g.add(j)
        pairs.append((pred[i], gold[j], round(s, 3)))
    p = len(pairs) / len(pred)
    r = len(pairs) / len(gold)
    return (round(2 * p * r / (p + r), 3) if p + r else 0.0), pairs

def _avg(lst):
    lst = [v for v in lst if v is not None]
    return round(sum(lst) / len(lst), 3) if lst else None

def _pct(lst):
    v = _avg(lst)
    return round(v * 100, 1) if v is not None else None


# ── per-file scoring ───────────────────────────────────────────────────────────
def score_file(result: dict, gold_row, model_id: str, backend: str,
               wall_sec: float, total_tokens: int) -> dict:
    """
    result   : dict returned by model_openai / model_qwen / model_llava run_file
    gold_row : pandas Series or None
    """
    p       = result["parsed"]
    skills  = p.get("predicted_skills", [])
    tokens  = result["prompt_tokens"] + result["completion_tokens"]
    latency = result["latency_sec"]

    is_valid = (
        result["parse_ok"]
        and p["difficulty_level"] in VALID_DIFFICULTY
        and isinstance(p["confidence"], float)
        and len(p["predicted_tags"]) > 0
        and len(skills) > 0
        and bool(p["notes"])
    )

    # cost
    if backend == "openai":
        cost = result.get("est_cost_usd", 0.0)
    else:
        share = tokens / max(1, total_tokens)
        cost  = round(share * (wall_sec / 3600) * GPU_COST_PER_HOUR_USD, 6)

    # tokens per second
    tok_per_sec = (round(result["completion_tokens"] / max(latency, 0.001), 2)
                   if latency > 0 else None)

    # retrieval quality (pool recall) — only when RAG was used
    rag_pool    = result.get("rag_pool")
    pool_recall = None
    if rag_pool is not None and gold_row is not None:
        from rag import retrieval_recall
        g_skills   = split_multi(gold_row.get("predicted_skills"))
        pool_recall = retrieval_recall(g_skills, rag_pool)

    # quality vs gold
    cls = tag_ov = tag_sem = tag_prec = tag_rec = None
    sk_jac = sk_rec = sk_prec = None

    if gold_row is not None:
        g_diff   = str(gold_row.get("difficulty_level", "")).strip().lower()
        g_tags   = split_multi(gold_row.get("predicted_tags"))
        g_skills = split_multi(gold_row.get("predicted_skills"))

        cls        = p["difficulty_level"].lower() == g_diff
        tag_ov     = jaccard(p["predicted_tags"], g_tags)
        tag_sem, _ = semantic_f1(p["predicted_tags"], g_tags)
        tag_prec   = precision(p["predicted_tags"], g_tags)
        tag_rec    = recall(p["predicted_tags"], g_tags)
        sk_jac     = jaccard(skills, g_skills)
        sk_rec     = recall(skills, g_skills)
        sk_prec    = precision(skills, g_skills)

    return {
        "model_name":            model_id,
        "predicted_tags":        " | ".join(p["predicted_tags"]),
        "difficulty_level":      p["difficulty_level"],
        "predicted_skills":      " | ".join(skills),
        "confidence":            p["confidence"],
        "notes":                 p["notes"],
        "content_summary":       p["content_summary"],
        "is_valid_output":       is_valid,
        "n_hallucinated_skills": p.get("n_halluc_skills", 0),
        "prompt_tokens":         result["prompt_tokens"],
        "completion_tokens":     result["completion_tokens"],
        "total_tokens":          tokens,
        "tokens_per_sec":        tok_per_sec,
        "latency_sec":           latency,
        "est_cost_usd":          cost,
        # quality metrics
        "difficulty_correct":    cls,
        "tag_overlap_strict":    tag_ov,
        "tag_semantic_f1":       tag_sem,
        "tag_precision":         tag_prec,
        "tag_recall":            tag_rec,
        "skill_mapping_jaccard": sk_jac,
        "skill_recall_at_4":     sk_rec,
        "skill_precision":       sk_prec,
        "pool_recall":           pool_recall,
    }


# ── aggregate across all files ─────────────────────────────────────────────────
def aggregate(scored_rows: list[dict], model_id: str, wall_sec: float) -> dict:
    n = len(scored_rows)
    if n == 0: return {}

    diff_acc   = _pct([r["difficulty_correct"]    for r in scored_rows])
    tag_strict = _pct([r["tag_overlap_strict"]     for r in scored_rows])
    tag_sem    = _pct([r["tag_semantic_f1"]        for r in scored_rows])
    tag_prec   = _pct([r["tag_precision"]          for r in scored_rows])
    tag_rec    = _pct([r["tag_recall"]             for r in scored_rows])
    sk_jac     = _pct([r["skill_mapping_jaccard"]  for r in scored_rows])
    sk_rec     = _pct([r["skill_recall_at_4"]      for r in scored_rows])
    sk_prec    = _pct([r["skill_precision"]        for r in scored_rows])
    pool_rec   = _pct([r["pool_recall"]            for r in scored_rows])

    tagging_acc = (round((diff_acc + tag_strict) / 2, 1)
                   if diff_acc is not None and tag_strict is not None else None)
    tagging_sem = (round((diff_acc + tag_sem) / 2, 1)
                   if diff_acc is not None and tag_sem is not None else None)

    validity   = round(100 * sum(r["is_valid_output"] for r in scored_rows) / n, 1)
    avg_lat    = round(sum(r["latency_sec"] for r in scored_rows) / n, 4)
    total_tok  = sum(r["total_tokens"] for r in scored_rows)
    total_cost = round(sum(r["est_cost_usd"] for r in scored_rows), 6)
    items_hr   = round(3600 / max(0.001, wall_sec / n), 1)
    n_halluc   = sum(r.get("n_hallucinated_skills", 0) for r in scored_rows)

    # extra metrics
    avg_tok_sec = _avg([r["tokens_per_sec"] for r in scored_rows])
    cost_per_1k = round(total_cost / max(1, n) * 1000, 4)

    # retrieval quality — real number when RAG enabled, N/A otherwise
    retrieval_quality = (f"{pool_rec}% pool recall"
                         if pool_rec is not None
                         else "N/A (full skills list in prompt)")

    return {
        "model_name":   model_id,
        "n_items":      n,
        # ── 7 required metrics ────────────────────────────────────────────────
        "tagging_classification_accuracy_pct":          tagging_acc,
        "skill_mapping_accuracy_pct":                   sk_jac,
        "retrieval_quality":                            retrieval_quality,
        "structured_output_validity_pct":               validity,
        "avg_latency_sec":                              avg_lat,
        "total_tokens":                                 total_tok,
        "est_total_cost_usd":                           total_cost,
        "est_items_per_hour":                           items_hr,
        # ── extra metrics ─────────────────────────────────────────────────────
        "tag_semantic_f1_pct":                          tag_sem,
        "tag_precision_pct":                            tag_prec,
        "tag_recall_pct":                               tag_rec,
        "skill_precision_pct":                          sk_prec,
        "avg_tokens_per_sec":                           avg_tok_sec,
        "est_cost_per_1000_files_usd":                  cost_per_1k,
        # ── diagnostics ───────────────────────────────────────────────────────
        "difficulty_accuracy_pct":                      diff_acc,
        "tag_overlap_strict_pct":                       tag_strict,
        "tagging_classification_accuracy_semantic_pct": tagging_sem,
        "skill_recall_at_n_pct":                        sk_rec,
        "n_hallucinated_skills":                        n_halluc,
        "wall_sec":                                     round(wall_sec, 2),
    }


# ── deployment readiness ───────────────────────────────────────────────────────
def readiness_check(agg: dict) -> list[dict]:
    checks = []
    def chk(key, op, thr, label):
        v = agg.get(key)
        if v is None or not isinstance(v, (int, float)):
            checks.append({"label": label, "status": "N/A",
                           "value": str(v), "threshold": thr})
            return
        ok = (v >= thr) if op == ">=" else (v <= thr)
        checks.append({"label": label,
                       "status": "PASS" if ok else "FAIL",
                       "value": v, "threshold": thr, "op": op})
    chk("structured_output_validity_pct", ">=", 95.0, "Structured-output validity (%)")
    chk("avg_latency_sec",               "<=", 10.0, "Average latency (s)")
    chk("skill_mapping_accuracy_pct",    ">=", 25.0, "Skill-mapping accuracy / Jaccard (%)")
    return checks
