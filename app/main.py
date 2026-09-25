"""
main.py — FastAPI application.

Routes
------
GET  /health                   service health + loaded models
GET  /v1/models                list available model IDs
POST /v1/tag/upload            tag ONE file (choose model via form field)
POST /v1/tag                   tag ONE file (choose model via body.model)
POST /v1/benchmark             run models on a list of files

Models supported
----------------
  openai  → gpt-4o-mini via api.openai.com
  qwen    → Qwen2.5-VL-3B-AWQ via vLLM AsyncLLMEngine on GPU

RAG
---
  Enabled via RAG_ENABLED = True in config.py (default: True).
  load_rag_index() called at startup to embed the 136-skill taxonomy.
  Each model call retrieves top-15 skills before prompting.

Run
---
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
"""
from __future__ import annotations
import os, math, time, tempfile, requests as _requests, re as _re
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from contextlib import asynccontextmanager

from schemas import (
    HealthResponse, ModelList, ModelCard,
    TagRequest, TagResult, BenchmarkRequest, BenchmarkReport, ModelAggregate,
)
from config import (
    OPENAI_MODEL, QWEN_MODEL_ID,
    SKILLS_CSV_PATH, VALID_DIFFICULTY, RAG_ENABLED,
)
from extractor import extract_content, build_digest
from prompts import SKILL_TAXONOMY, SKILLS_BLOCK, ground_skills
from scorer import score_file, aggregate, readiness_check

GOLD_SET_PATH = os.getenv(
    "GOLD_SET_PATH",
    os.path.join(os.path.dirname(__file__), "../data/Golden-set-Reviewed.xlsx")
)
GOLD_SET: dict = {}

VALID_MODELS = {"openai", "qwen"}

def split_multi(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return []
    return [x.strip() for x in _re.split(r"\s*\|\s*|\s*;\s*", str(v)) if x.strip()]


# ── startup ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global GOLD_SET
    print(f"[startup] skills loaded: {len(SKILL_TAXONOMY)} entries")

    if GOLD_SET_PATH and os.path.exists(GOLD_SET_PATH):
        df = pd.read_excel(GOLD_SET_PATH)
        def fkey(n): return _re.sub(r"[^a-z0-9.]", "",
                                    os.path.basename(str(n)).lower())
        GOLD_SET = {fkey(r["file_name"]): r for _, r in df.iterrows()}
        print(f"[startup] gold set: {len(GOLD_SET)} rows")
    else:
        print("[startup] no gold set — accuracy metrics will be null")

    if RAG_ENABLED:
        from rag import load_rag_index
        load_rag_index()
        print("[startup] RAG index ready")

    # Qwen AsyncLLMEngine loads on first request
    # avoids CUDA init conflict during async lifespan

    yield
    print("[shutdown] bye")

app = FastAPI(title="Content Tagging & Competency Mapping API",
              version="1.0.0", lifespan=lifespan)


# ── helpers ───────────────────────────────────────────────────────────────────
def _fkey(name):
    return _re.sub(r"[^a-z0-9.]", "", os.path.basename(str(name)).lower())

def _gold_for(filename):
    return GOLD_SET.get(_fkey(filename))

def _model_id(model_key: str) -> str:
    return {"openai": OPENAI_MODEL,
            "qwen":   QWEN_MODEL_ID}.get(model_key, model_key)

def _download_or_save(file_url, file_b64, filename) -> str:
    import base64
    tmp = tempfile.NamedTemporaryFile(
        suffix=os.path.splitext(filename)[1], delete=False)
    if file_b64:
        tmp.write(base64.b64decode(file_b64))
    elif file_url:
        resp = _requests.get(file_url, timeout=30)
        resp.raise_for_status()
        tmp.write(resp.content)
    else:
        raise HTTPException(400, "Provide file_url or file_b64")
    tmp.close()
    return tmp.name

def _run_one(extracted, filename, model_key, wall_tracker):
    if model_key not in VALID_MODELS:
        raise HTTPException(400,
            f"Unknown model '{model_key}'. Use: {', '.join(sorted(VALID_MODELS))}")
    if model_key == "openai":
        from model_openai import run_file
    elif model_key == "qwen":
        from model_qwen import run_file
    t0 = time.perf_counter()
    result = run_file(extracted, filename)
    wall_tracker.append(time.perf_counter() - t0)
    return result

def _build_tag_result(filename, content_type, result, model_id,
                      wall_sec, total_tokens) -> TagResult:
    gold   = _gold_for(filename)
    scored = score_file(result, gold, model_id, backend="",
                        wall_sec=wall_sec, total_tokens=total_tokens)
    scored["file_name"]    = filename
    scored["content_type"] = content_type
    return TagResult(**{k: scored.get(k) for k in TagResult.model_fields})


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health():
    return HealthResponse(
        status="ok",
        models=[OPENAI_MODEL, QWEN_MODEL_ID])


@app.get("/v1/models", response_model=ModelList, tags=["meta"])
def list_models():
    return ModelList(data=[
        ModelCard(id=OPENAI_MODEL),
        ModelCard(id=QWEN_MODEL_ID),
    ])


@app.post("/v1/tag", response_model=TagResult, tags=["tagging"])
def tag_file(req: TagRequest):
    """Tag ONE file. model: 'openai' | 'qwen' (default: 'qwen')"""
    tmp_path = _download_or_save(req.file_url, req.file_b64, req.filename)
    try:
        extracted = extract_content(tmp_path)
    finally:
        os.unlink(tmp_path)
    wall_tracker = []
    result    = _run_one(extracted, req.filename, req.model, wall_tracker)
    wall_sec  = wall_tracker[0] if wall_tracker else result["latency_sec"]
    total_tok = result["prompt_tokens"] + result["completion_tokens"]
    return _build_tag_result(req.filename, extracted["content_type"],
                             result, _model_id(req.model), wall_sec, total_tok)


@app.post("/v1/tag/upload", response_model=TagResult, tags=["tagging"])
async def tag_file_upload(file: UploadFile = File(...),
                          model: str = Form("qwen")):
    """Tag ONE file uploaded directly. model: 'openai' | 'qwen'"""
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        extracted = extract_content(tmp_path)
    finally:
        os.unlink(tmp_path)
    wall_tracker = []
    result    = _run_one(extracted, file.filename, model, wall_tracker)
    wall_sec  = wall_tracker[0] if wall_tracker else result["latency_sec"]
    total_tok = result["prompt_tokens"] + result["completion_tokens"]
    return _build_tag_result(file.filename, extracted["content_type"],
                             result, _model_id(model), wall_sec, total_tok)


@app.post("/v1/benchmark", response_model=BenchmarkReport, tags=["benchmark"])
def benchmark(req: BenchmarkRequest):
    """Run openai and qwen on every file and return full benchmark report."""
    if len(req.file_urls) != len(req.filenames):
        raise HTTPException(400, "file_urls and filenames must be the same length")

    extracted_list = []
    for url, fname in zip(req.file_urls, req.filenames):
        tmp_path = _download_or_save(url, None, fname)
        try:
            extracted_list.append((fname, extract_content(tmp_path)))
        finally:
            os.unlink(tmp_path)

    all_results:    list[TagResult]      = []
    all_aggregates: list[ModelAggregate] = []

    model_pairs = [
        ("openai", OPENAI_MODEL),
        ("qwen",   QWEN_MODEL_ID),
    ]

    for model_key, model_id in model_pairs:
        scored_rows, wall_times, total_toks = [], [], []
        for fname, extracted in extracted_list:
            wall_tracker = []
            try:
                result = _run_one(extracted, fname, model_key, wall_tracker)
            except Exception as e:
                result = {
                    "parsed": {"content_summary": "", "predicted_tags": [],
                               "difficulty_level": "", "predicted_skills": [],
                               "n_halluc_skills": 0, "confidence": None, "notes": ""},
                    "parse_ok": False, "raw_text": str(e),
                    "prompt_tokens": 0, "completion_tokens": 0,
                    "latency_sec": 0.0, "est_cost_usd": 0.0,
                    "rag_pool": None,
                }
                wall_tracker = [0.0]
            wall_sec  = wall_tracker[0] if wall_tracker else result["latency_sec"]
            total_tok = result["prompt_tokens"] + result["completion_tokens"]
            wall_times.append(wall_sec)
            total_toks.append(total_tok)
            gold   = _gold_for(fname)
            scored = score_file(result, gold, model_id,
                                backend=model_key,
                                wall_sec=sum(wall_times),
                                total_tokens=sum(total_toks))
            scored["file_name"]    = fname
            scored["content_type"] = extracted["content_type"]
            scored_rows.append(scored)
            all_results.append(
                TagResult(**{k: scored.get(k) for k in TagResult.model_fields}))

        agg = aggregate(scored_rows, model_id, wall_sec=sum(wall_times))
        agg["readiness"] = readiness_check(agg)
        all_aggregates.append(
            ModelAggregate(**{k: agg.get(k) for k in ModelAggregate.model_fields}))

    best = max(all_aggregates,
               key=lambda a: a.tagging_classification_accuracy_pct or 0)
    return BenchmarkReport(
        results=all_results,
        aggregates=all_aggregates,
        winner=best.model_name,
    )


@app.get("/v1/benchmark/summary", tags=["benchmark"])
def benchmark_summary():
    return {
        "metrics": [
            "tagging_classification_accuracy_pct",
            "skill_mapping_accuracy_pct",
            "retrieval_quality",
            "structured_output_validity_pct",
            "avg_latency_sec",
            "total_tokens / est_total_cost_usd",
            "est_items_per_hour",
            "tag_precision_pct",
            "tag_recall_pct",
            "skill_precision_pct",
            "avg_tokens_per_sec",
            "est_cost_per_1000_files_usd",
        ],
        "models": [OPENAI_MODEL, QWEN_MODEL_ID],
        "rag_enabled": RAG_ENABLED,
        "note": "POST /v1/benchmark to run the full comparison.",
    }