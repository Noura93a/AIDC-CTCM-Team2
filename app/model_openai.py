"""
model_openai.py — OpenAI backend (gpt-4o-mini or any OpenAI model).
Mirrors the exact logic from the working Colab notebook (openai.ipynb).
"""
from __future__ import annotations
import base64, io, json, re, time
from PIL import Image
from openai import OpenAI
from config import (
    OPENAI_MODEL, OPENAI_API_KEY,
    MAX_IMAGES_PER_FILE, DIFF_EXCERPT_CHARS,
    OPENAI_INPUT_COST_PER_1K, OPENAI_OUTPUT_COST_PER_1K,
    VALID_DIFFICULTY, MAX_NEW_TOKENS,
)
from prompts import (
    SYSTEM_PROMPT, USER_TEMPLATE, DIFF_SYSTEM_PROMPT, DIFF_USER_TEMPLATE,
    format_label, ground_skills, norm_skill,
)
from extractor import build_digest

_client: OpenAI | None = None

def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _image_to_data_url(img) -> str:
    if isinstance(img, (str, bytes)):
        img = Image.open(io.BytesIO(img) if isinstance(img, bytes) else img)
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


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
        "content_summary":  str(p.get("content_summary", "")).strip(),
        "predicted_tags":   clean,
        "difficulty_level": diff,
        "predicted_skills": skills,
        "n_halluc_skills":  n_halluc,
        "confidence":       conf,
        "notes":            str(notes).strip(),
    }


def run_file(extracted: dict, filename: str) -> dict:
    """Tag one file via OpenAI. Returns raw dict with parsed output + token counts."""
    client = get_client()
    ext = extracted["content_type"]
    digest, note = build_digest(extracted["text"], ext)
    images = extracted["images"][:MAX_IMAGES_PER_FILE]
    img_note = f"\n{len(images)} image(s) attached -- read them too." if images else ""

    user_text = USER_TEMPLATE.format(
        fmt=format_label(ext), note=note, img_note=img_note, digest=digest)

    content = []
    for img in images:
        content.append({"type": "image_url",
                        "image_url": {"url": _image_to_data_url(img), "detail": "auto"}})
    content.append({"type": "text", "text": user_text})

    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": content},
        ],
        max_tokens=MAX_NEW_TOKENS,
        temperature=0,
    )
    latency = time.perf_counter() - t0

    raw_text = resp.choices[0].message.content or ""
    obj, ok = _parse_json(raw_text)
    parsed = _normalize_output(obj)
    prompt_tok  = resp.usage.prompt_tokens
    compl_tok   = resp.usage.completion_tokens

    # Pass 2: difficulty refinement
    half = DIFF_EXCERPT_CHARS // 2
    excerpt = (digest[:half] + "\n[...]\n" + digest[-half:]) if len(digest) > DIFF_EXCERPT_CHARS else digest
    diff_resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": DIFF_SYSTEM_PROMPT},
            {"role": "user",   "content": DIFF_USER_TEMPLATE.format(
                fmt=format_label(ext), excerpt=excerpt)},
        ],
        max_tokens=80,
        temperature=0,
    )
    diff_obj, _ = _parse_json(diff_resp.choices[0].message.content or "")
    diff_label = str(diff_obj.get("difficulty_level", "")).strip().title()
    if diff_label in VALID_DIFFICULTY:
        parsed["difficulty_level"] = diff_label
    prompt_tok  += diff_resp.usage.prompt_tokens
    compl_tok   += diff_resp.usage.completion_tokens

    cost = (prompt_tok / 1000 * OPENAI_INPUT_COST_PER_1K
            + compl_tok / 1000 * OPENAI_OUTPUT_COST_PER_1K)

    return {
        "parsed":             parsed,
        "parse_ok":           ok,
        "raw_text":           raw_text,
        "prompt_tokens":      prompt_tok,
        "completion_tokens":  compl_tok,
        "latency_sec":        round(latency, 4),
        "est_cost_usd":       round(cost, 6),
    }
