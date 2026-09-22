"""
model_qwen.py — Qwen2.5-VL-3B-AWQ backend via vLLM.
Mirrors the working no-RAG Colab notebook (content_tagging_qwen3b_no_rag__2_.ipynb).
The engine is loaded once at startup and stays in GPU memory.
"""
from __future__ import annotations
import json, re, time, gc
import torch
from vllm import LLM, SamplingParams
from transformers import AutoProcessor
from config import (
    QWEN_MODEL_ID, QWEN_QUANT, QWEN_VISION,
    MAX_MODEL_LEN, GPU_MEM_UTIL, ENFORCE_EAGER,
    MAX_IMAGES_PER_FILE, MAX_IMAGE_DIM, MAX_NEW_TOKENS,
    VALID_DIFFICULTY, DIFF_EXCERPT_CHARS, REPETITION_PENALTY,
    GPU_COST_PER_HOUR_USD,
)
from prompts import (
    SYSTEM_PROMPT, USER_TEMPLATE, DIFF_SYSTEM_PROMPT, DIFF_USER_TEMPLATE,
    format_label, ground_skills,
)
from extractor import build_digest

# ── engine singleton ──────────────────────────────────────────────────────────
_llm: LLM | None = None
_proc = None

def get_engine():
    global _llm, _proc
    if _llm is None:
        gc.collect()
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        kwargs = dict(
            model=QWEN_MODEL_ID,
            max_model_len=MAX_MODEL_LEN,
            gpu_memory_utilization=GPU_MEM_UTIL,
            dtype="half",
            enforce_eager=ENFORCE_EAGER,
            trust_remote_code=True,
        )
        if QWEN_QUANT:
            kwargs["quantization"] = QWEN_QUANT
        if QWEN_VISION:
            kwargs["limit_mm_per_prompt"] = {"image": MAX_IMAGES_PER_FILE}
            kwargs["mm_processor_kwargs"] = {"max_pixels": MAX_IMAGE_DIM * MAX_IMAGE_DIM}
        _llm  = LLM(**kwargs)
        _proc = AutoProcessor.from_pretrained(QWEN_MODEL_ID, trust_remote_code=True)
        print(f"[Qwen] engine loaded: {QWEN_MODEL_ID}")
    return _llm, _proc


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
    toks = [w[:-1] if len(w)>3 and w.endswith("s") and not w.endswith(("ss","is","us")) else w
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
        diff = next((d for d in VALID_DIFFICULTY if diff[:3] and d.startswith(diff[:3])), diff)
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
        "content_summary":  str(p.get("content_summary","")).strip(),
        "predicted_tags":   clean,
        "difficulty_level": diff,
        "predicted_skills": skills,
        "n_halluc_skills":  n_halluc,
        "confidence":       conf,
        "notes":            str(notes).strip(),
    }


def _build_prompt(extracted: dict, filename: str, proc) -> dict:
    ext = extracted["content_type"]
    digest, note = build_digest(extracted["text"], ext)
    images = extracted["images"][:MAX_IMAGES_PER_FILE] if QWEN_VISION else []
    img_note = f"\n{len(images)} image(s) attached -- read them too." if images else ""
    user_text = USER_TEMPLATE.format(
        fmt=format_label(ext), note=note, img_note=img_note, digest=digest)
    if QWEN_VISION and images:
        content = [{"type":"image","image":img} for img in images] + [{"type":"text","text":user_text}]
        messages = [
            {"role":"system","content":[{"type":"text","text":SYSTEM_PROMPT}]},
            {"role":"user",  "content":content},
        ]
    else:
        messages = [
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user",  "content":user_text},
        ]
    req = {"prompt": proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)}
    if QWEN_VISION and images:
        req["multi_modal_data"] = {"image": images}
    return req


def _build_diff_prompt(extracted: dict, proc) -> dict:
    ext = extracted["content_type"]
    digest, _ = build_digest(extracted["text"], ext)
    half = DIFF_EXCERPT_CHARS // 2
    excerpt = (digest[:half] + "\n[...]\n" + digest[-half:]) if len(digest) > DIFF_EXCERPT_CHARS else digest
    messages = [
        {"role":"system","content":DIFF_SYSTEM_PROMPT},
        {"role":"user",  "content":DIFF_USER_TEMPLATE.format(fmt=format_label(ext), excerpt=excerpt)},
    ]
    return {"prompt": proc.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)}


def run_file(extracted: dict, filename: str) -> dict:
    """Tag one file via Qwen. Loads engine on first call (warm thereafter)."""
    llm, proc = get_engine()
    sp      = _make_params(MAX_NEW_TOKENS)
    sp_diff = _make_params(80)

    req = _build_prompt(extracted, filename, proc)

    t0 = time.perf_counter()
    outs = llm.generate([req], sp, use_tqdm=False)
    latency = time.perf_counter() - t0

    out = outs[0]
    obj, ok = _parse_json(out.outputs[0].text)
    parsed = _normalize_output(obj)
    prompt_tok = len(out.prompt_token_ids)
    compl_tok  = len(out.outputs[0].token_ids)

    # retry if empty
    if not parsed["predicted_tags"]:
        sp_plain = SamplingParams(temperature=0.0, max_tokens=MAX_NEW_TOKENS,
                                  repetition_penalty=REPETITION_PENALTY)
        retry = llm.generate([req], sp_plain, use_tqdm=False)
        obj2, ok2 = _parse_json(retry[0].outputs[0].text)
        p2 = _normalize_output(obj2)
        if p2["predicted_tags"]:
            parsed, ok = p2, ok2
        prompt_tok += len(retry[0].prompt_token_ids)
        compl_tok  += len(retry[0].outputs[0].token_ids)

    # pass 2: difficulty
    diff_req  = _build_diff_prompt(extracted, proc)
    t_diff = time.perf_counter()
    diff_out  = llm.generate([diff_req], sp_diff, use_tqdm=False)
    latency  += time.perf_counter() - t_diff
    diff_obj, _ = _parse_json(diff_out[0].outputs[0].text)
    diff_label  = str(diff_obj.get("difficulty_level","")).strip().title()
    if diff_label in VALID_DIFFICULTY:
        parsed["difficulty_level"] = diff_label
    prompt_tok += len(diff_out[0].prompt_token_ids)
    compl_tok  += len(diff_out[0].outputs[0].token_ids)

    # cost estimate (GPU time share is approximated per token)
    cost = 0.0   # set properly in scorer using wall time

    return {
        "parsed":             parsed,
        "parse_ok":           ok,
        "raw_text":           out.outputs[0].text,
        "prompt_tokens":      prompt_tok,
        "completion_tokens":  compl_tok,
        "latency_sec":        round(latency, 4),
        "est_cost_usd":       cost,
    }
