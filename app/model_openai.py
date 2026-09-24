"""
model_openai.py — OpenAI backend (gpt-4o-mini or any OpenAI model).

3-pass flow:
  pass 1 → full 136-skill list → get tags + initial skills
  pass 2 → RAG using tags from pass 1 → re-pick skills from relevant pool
  pass 3 → difficulty refinement

RAG on pass 2 only (after tags are known) gives much better pool recall
than RAG on pass 1 (no tags = weak retrieval signal).
"""
from __future__ import annotations
import base64, io, json, re, time
from PIL import Image
from openai import OpenAI
from config import (
    OPENAI_MODEL, OPENAI_API_KEY,
    MAX_IMAGES_PER_FILE, DIFF_EXCERPT_CHARS,
    OPENAI_INPUT_COST_PER_1K, OPENAI_OUTPUT_COST_PER_1K,
    VALID_DIFFICULTY, MAX_NEW_TOKENS, RAG_ENABLED,
)
from prompts import (
    SYSTEM_PROMPT, USER_TEMPLATE, DIFF_SYSTEM_PROMPT, DIFF_USER_TEMPLATE,
    format_label, ground_skills, build_rag_system_prompt,
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


def _build_messages(extracted: dict, system_prompt: str) -> list:
    ext = extracted["content_type"]
    digest, note = build_digest(extracted["text"], ext)
    images   = extracted["images"][:MAX_IMAGES_PER_FILE]
    img_note = f"\n{len(images)} image(s) attached -- read them too." if images else ""
    user_text = USER_TEMPLATE.format(
        fmt=format_label(ext), note=note,
        img_note=img_note, digest=digest)
    content = []
    for img in images:
        content.append({"type": "image_url",
                        "image_url": {"url": _image_to_data_url(img),
                                      "detail": "auto"}})
    content.append({"type": "text", "text": user_text})
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": content},
    ]


def run_file(extracted: dict, filename: str) -> dict:
    """
    3-pass flow:
      pass 1 → full skill list → get tags + initial skills
      pass 2 → RAG using tags  → re-pick skills from relevant pool
      pass 3 → difficulty refinement
    """
    client = get_client()
    ext    = extracted["content_type"]

    # ── pass 1: full skill list → tags + initial skills ───────────────────────
    messages = _build_messages(extracted, SYSTEM_PROMPT)

    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        max_tokens=MAX_NEW_TOKENS,
        temperature=0,
    )
    latency = time.perf_counter() - t0

    raw_text   = resp.choices[0].message.content or ""
    obj, ok    = _parse_json(raw_text)
    parsed     = _normalize_output(obj)
    prompt_tok = resp.usage.prompt_tokens
    compl_tok  = resp.usage.completion_tokens

    # ── pass 2: RAG using tags from pass 1 → re-pick skills ──────────────────
    rag_pool = None
    if RAG_ENABLED and parsed["predicted_tags"]:
        from rag import retrieve_skills
        rag_pool = retrieve_skills(
            content_text=extracted["text"],
            tags=parsed["predicted_tags"],
            summary=parsed["content_summary"],
        )
        rag_system    = build_rag_system_prompt(rag_pool)
        skill_msgs    = _build_messages(extracted, rag_system)
        t_rag         = time.perf_counter()
        skill_resp    = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=skill_msgs,
            max_tokens=MAX_NEW_TOKENS,
            temperature=0,
        )
        latency      += time.perf_counter() - t_rag
        skill_obj, _  = _parse_json(skill_resp.choices[0].message.content or "")
        skill_parsed  = _normalize_output(skill_obj)
        if skill_parsed["predicted_skills"]:
            parsed["predicted_skills"] = skill_parsed["predicted_skills"]
            parsed["n_halluc_skills"]  = skill_parsed["n_halluc_skills"]
        prompt_tok += skill_resp.usage.prompt_tokens
        compl_tok  += skill_resp.usage.completion_tokens

    # ── pass 3: difficulty refinement ─────────────────────────────────────────
    digest, _ = build_digest(extracted["text"], ext)
    half      = DIFF_EXCERPT_CHARS // 2
    excerpt   = (digest[:half] + "\n[...]\n" + digest[-half:]
                 if len(digest) > DIFF_EXCERPT_CHARS else digest)
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
    diff_label  = str(diff_obj.get("difficulty_level", "")).strip().title()
    if diff_label in VALID_DIFFICULTY:
        parsed["difficulty_level"] = diff_label
    prompt_tok += diff_resp.usage.prompt_tokens
    compl_tok  += diff_resp.usage.completion_tokens

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
        "rag_pool":           rag_pool,
    }