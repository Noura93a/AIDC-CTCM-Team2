"""
model_qwen.py — Qwen2.5-VL-3B-AWQ backend via vLLM AsyncLLMEngine.

AsyncLLMEngine enables:
  - paged attention:      KV cache in fixed pages, no memory waste
  - continuous batching:  new requests join mid-generation automatically
  - async generation:     concurrent requests processed together

3-pass flow:
  pass 1 → full 136-skill list → get tags + initial skills
  pass 2 → RAG using tags from pass 1 → re-pick skills from pool
  pass 3 → difficulty refinement
"""
from __future__ import annotations
import json, re, time, gc, asyncio, uuid
import torch
from vllm import AsyncLLMEngine, AsyncEngineArgs, SamplingParams
from transformers import AutoProcessor
from config import (
    QWEN_MODEL_ID, QWEN_QUANT, QWEN_VISION,
    MAX_MODEL_LEN, GPU_MEM_UTIL, ENFORCE_EAGER,
    MAX_IMAGES_PER_FILE, MAX_IMAGE_DIM, MAX_NEW_TOKENS,
    VALID_DIFFICULTY, DIFF_EXCERPT_CHARS, REPETITION_PENALTY,
    GPU_COST_PER_HOUR_USD, RAG_ENABLED,
)
from prompts import (
    SYSTEM_PROMPT, USER_TEMPLATE, DIFF_SYSTEM_PROMPT, DIFF_USER_TEMPLATE,
    format_label, ground_skills, build_rag_system_prompt,
)
from extractor import build_digest

# ── engine singleton ──────────────────────────────────────────────────────────
_engine = None
_proc   = None

def get_engine():
    global _engine, _proc
    if _engine is None:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        engine_args = AsyncEngineArgs(
            model=QWEN_MODEL_ID,
            max_model_len=MAX_MODEL_LEN,
            gpu_memory_utilization=GPU_MEM_UTIL,
            dtype="half",
            enforce_eager=ENFORCE_EAGER,
            trust_remote_code=True,
            quantization=QWEN_QUANT if QWEN_QUANT else None,
            limit_mm_per_prompt={"image": MAX_IMAGES_PER_FILE} if QWEN_VISION else None,
            mm_processor_kwargs={"max_pixels": MAX_IMAGE_DIM * MAX_IMAGE_DIM} if QWEN_VISION else None,
            disable_log_requests=True,
        )

        _engine = AsyncLLMEngine.from_engine_args(engine_args)
        _proc   = AutoProcessor.from_pretrained(
            QWEN_MODEL_ID, trust_remote_code=True)
        print(f"[Qwen] AsyncLLMEngine loaded: {QWEN_MODEL_ID}")
    return _engine, _proc


def _make_params(max_tokens: int) -> SamplingParams:
    return SamplingParams(
        temperature=0.0,
        max_tokens=max_tokens,
        repetition_penalty=REPETITION_PENALTY,
    )


def _parse_json(raw: str) -> tuple[dict, bool]:
    s = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", (raw or "").strip())
    for candidate in (s, (re.search(r"\{.*\}", s, re.S) or [None])[0]):
        if candidate:
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict): return obj, True
            except Exception: pass
    return {}, False


def _norm_label(t: str) -> str:
    t = str(t).lower().replace("&", " and ")
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    toks = [w[:-1] if len(w)>3 and w.endswith("s")
            and not w.endswith(("ss","is","us")) else w
            for w in t.split()]
    return " ".join(toks)


def _normalize_output(p: dict) -> dict:
    p = p if isinstance(p, dict) else {}
    tags = p.get("predicted_tags", [])
    if isinstance(tags, str): tags = re.split(r"[;|\n]", tags)
    clean, seen = [], set()
    for t in tags:
        t = str(t).strip().strip('"').strip()
        k = _norm_label(t)
        if t and k and k not in seen:
            seen.add(k); clean.append(t[:80])
    diff = str(p.get("difficulty_level", "")).strip().title()
    if diff not in VALID_DIFFICULTY:
        diff = next((d for d in VALID_DIFFICULTY
                     if diff[:3] and d.startswith(diff[:3])), diff)
    conf = p.get("confidence")
    try:
        conf = float(conf)
        if 1.0 < conf <= 100.0: conf /= 100.0
        conf = round(min(1.0, max(0.0, conf)), 3)
    except (TypeError, ValueError): conf = None
    notes = p.get("notes", "")
    if isinstance(notes, list): notes = " • ".join(str(x).strip() for x in notes)
    raw_skills = p.get("predicted_skills", [])
    if isinstance(raw_skills, str): raw_skills = re.split(r"[;|\n]", raw_skills)
    skills, n_halluc = ground_skills(raw_skills)
    return {
        "content_summary":  str(p.get("content_summary", "")).strip(),
        "predicted_tags":   clean,
        "difficulty_level": diff,
        "predicted_skills": skills,
        "n_halluc_skills":  n_halluc,
        "confidence":       conf,
        "notes":            str(notes).strip(),
    }


def _build_prompt(extracted: dict, system_prompt: str, proc) -> dict:
    ext = extracted["content_type"]
    digest, note = build_digest(extracted["text"], ext)
    images = extracted["images"][:MAX_IMAGES_PER_FILE] if QWEN_VISION else []
    img_note = f"\n{len(images)} image(s) attached -- read them too." if images else ""
    user_text = USER_TEMPLATE.format(
        fmt=format_label(ext), note=note,
        img_note=img_note, digest=digest)
    if QWEN_VISION and images:
        content = ([{"type": "image", "image": img} for img in images]
                   + [{"type": "text", "text": user_text}])
        messages = [
            {"role": "system",
             "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": content},
        ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_text},
        ]
    req = {"prompt": proc.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True)}
    if QWEN_VISION and images:
        req["multi_modal_data"] = {"image": images}
    return req


def _build_skill_prompt(extracted: dict, rag_system: str, proc) -> dict:
    ext = extracted["content_type"]
    digest, note = build_digest(extracted["text"], ext)
    user_text = USER_TEMPLATE.format(
        fmt=format_label(ext), note=note,
        img_note="", digest=digest)
    messages = [
        {"role": "system", "content": rag_system},
        {"role": "user",   "content": user_text},
    ]
    return {"prompt": proc.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True)}


def _build_diff_prompt(extracted: dict, proc) -> dict:
    ext = extracted["content_type"]
    digest, _ = build_digest(extracted["text"], ext)
    half    = DIFF_EXCERPT_CHARS // 2
    excerpt = (digest[:half] + "\n[...]\n" + digest[-half:]
               if len(digest) > DIFF_EXCERPT_CHARS else digest)
    messages = [
        {"role": "system", "content": DIFF_SYSTEM_PROMPT},
        {"role": "user",   "content": DIFF_USER_TEMPLATE.format(
            fmt=format_label(ext), excerpt=excerpt)},
    ]
    return {"prompt": proc.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True)}


async def _generate(engine, req: dict,
                    params: SamplingParams) -> tuple[str, int, int]:
    """
    Submit one request to AsyncLLMEngine and collect the final output.
    Paged attention + continuous batching happen automatically inside vLLM.
    Multiple concurrent calls to _generate() are batched together by vLLM.
    Returns (text, prompt_tokens, completion_tokens).
    """
    request_id   = str(uuid.uuid4())
    prompt_input = req.get("prompt")
    mm_data      = req.get("multi_modal_data")

    if mm_data:
        results_generator = engine.generate(
            {"prompt": prompt_input, "multi_modal_data": mm_data},
            sampling_params=params,
            request_id=request_id,
        )
    else:
        results_generator = engine.generate(
            prompt_input,
            sampling_params=params,
            request_id=request_id,
        )

    final_output = None
    async for output in results_generator:
        final_output = output

    if final_output is None:
        return "", 0, 0

    text        = final_output.outputs[0].text
    prompt_toks = len(final_output.prompt_token_ids)
    compl_toks  = len(final_output.outputs[0].token_ids)
    return text, prompt_toks, compl_toks


async def run_file_async(extracted: dict, filename: str) -> dict:
    """
    3-pass async flow using AsyncLLMEngine.
    Multiple concurrent calls benefit from continuous batching:
      - vLLM batches tokens from concurrent requests together
      - paged attention manages KV cache pages efficiently
      - throughput improves significantly under concurrent load
    """
    engine, proc = get_engine()
    sp      = _make_params(MAX_NEW_TOKENS)
    sp_diff = _make_params(80)

    # ── pass 1: full skill list → tags + initial skills ───────────────────────
    req = _build_prompt(extracted, SYSTEM_PROMPT, proc)

    t0 = time.perf_counter()
    text, prompt_tok, compl_tok = await _generate(engine, req, sp)
    latency = time.perf_counter() - t0

    obj, ok = _parse_json(text)
    parsed  = _normalize_output(obj)

    # retry if empty output
    if not parsed["predicted_tags"]:
        text2, pt2, ct2 = await _generate(engine, req, sp)
        obj2, ok2 = _parse_json(text2)
        p2 = _normalize_output(obj2)
        if p2["predicted_tags"]:
            parsed, ok = p2, ok2
        prompt_tok += pt2
        compl_tok  += ct2

    # ── pass 2: RAG using tags from pass 1 → re-pick skills ──────────────────
    rag_pool = None
    if RAG_ENABLED and parsed["predicted_tags"]:
        from rag import retrieve_skills
        rag_pool     = retrieve_skills(
            content_text=extracted["text"],
            tags=parsed["predicted_tags"],
            summary=parsed["content_summary"],
        )
        rag_system   = build_rag_system_prompt(rag_pool)
        skill_req    = _build_skill_prompt(extracted, rag_system, proc)
        t_rag        = time.perf_counter()
        skill_text, pt_rag, ct_rag = await _generate(engine, skill_req, sp)
        latency     += time.perf_counter() - t_rag
        skill_obj, _ = _parse_json(skill_text)
        skill_parsed = _normalize_output(skill_obj)
        if skill_parsed["predicted_skills"]:
            parsed["predicted_skills"] = skill_parsed["predicted_skills"]
            parsed["n_halluc_skills"]  = skill_parsed["n_halluc_skills"]
        prompt_tok += pt_rag
        compl_tok  += ct_rag

    # ── pass 3: difficulty refinement ─────────────────────────────────────────
    diff_req = _build_diff_prompt(extracted, proc)
    t_diff   = time.perf_counter()
    diff_text, pt_diff, ct_diff = await _generate(engine, diff_req, sp_diff)
    latency += time.perf_counter() - t_diff
    diff_obj, _ = _parse_json(diff_text)
    diff_label  = str(diff_obj.get("difficulty_level", "")).strip().title()
    if diff_label in VALID_DIFFICULTY:
        parsed["difficulty_level"] = diff_label
    prompt_tok += pt_diff
    compl_tok  += ct_diff

    return {
        "parsed":             parsed,
        "parse_ok":           ok,
        "raw_text":           text,
        "prompt_tokens":      prompt_tok,
        "completion_tokens":  compl_tok,
        "latency_sec":        round(latency, 4),
        "est_cost_usd":       0.0,
        "rag_pool":           rag_pool,
    }


def run_file(extracted: dict, filename: str) -> dict:
    """
    Sync wrapper called by main.py.
    Runs the async 3-pass flow in a clean event loop.
    AsyncLLMEngine handles concurrent batching internally.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    run_file_async(extracted, filename))
                return future.result()
        else:
            return loop.run_until_complete(
                run_file_async(extracted, filename))
    except RuntimeError:
        return asyncio.run(run_file_async(extracted, filename))