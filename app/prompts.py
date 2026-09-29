"""
prompts.py — system prompts, user templates, skill taxonomy loading.
Same prompts used for OpenAI, Qwen, and LLaVA so results are comparable.
"""
from __future__ import annotations
import os, re, difflib
import pandas as pd
from config import SKILLS_CSV_PATH, N_OUTPUT_SKILLS, MAX_TAGS, VALID_DIFFICULTY

# ── format labels ─────────────────────────────────────────────────────────────
FORMAT_LABELS = {
    "pptx":"slide deck","ppt":"slide deck","odp":"slide deck","key":"slide deck",
    "ipynb":"Jupyter notebook (lecture / lab)","md":"Markdown document / lab sheet",
    "docx":"Word document","doc":"Word document","odt":"text document","rtf":"text document",
    "pdf":"PDF document","epub":"e-book",
    "xlsx":"spreadsheet (may be a quiz or question bank)",
    "xls":"spreadsheet (may be a quiz or question bank)",
    "csv":"tabular data / question bank","html":"web page","txt":"plain-text document",
    "py":"Python script","sql":"SQL script","mp4":"video transcript","mp3":"audio transcript",
    "png":"image","jpg":"image","jpeg":"image","zip":"archive of learning materials",
}

def format_label(ext: str) -> str:
    return f"{FORMAT_LABELS.get(ext, 'file')} (.{ext})"


# ── skill taxonomy ────────────────────────────────────────────────────────────
def load_skills(path: str = SKILLS_CSV_PATH):
    if not os.path.exists(path):
        return [], [], ""
    df = pd.read_csv(path)
    df["skill_name"] = df["skill_name"].astype(str).str.strip()
    df = df.drop_duplicates(subset=["skill_name"]).reset_index(drop=True)
    taxonomy = [
        {
            "id":          str(getattr(r, "skill_id", i + 1)),
            "name":        r.skill_name,
            "description": str(r.description).strip(),
            "prioritized": str(getattr(r, "prioritized", "")).strip(),
        }
        for i, r in enumerate(df.itertuples(index=False))
    ]
    names = [s["name"] for s in taxonomy]
    block = "\n".join(
        f"{i+1:3}. {s['name']} -- {s['description'][:110]}"
        for i, s in enumerate(taxonomy)
    )
    return taxonomy, names, block

SKILL_TAXONOMY, SKILL_NAMES, SKILLS_BLOCK = load_skills()


def norm_skill(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()

def ground_skills(raw_list, n: int = N_OUTPUT_SKILLS):
    """Accept only taxonomy names; fuzzy-match near-misses; backfill from list order."""
    if isinstance(raw_list, str):
        raw_list = re.split(r"\s*[;|\n]\s*", raw_list)
    lookup = {norm_skill(s["name"]): s["name"] for s in SKILL_TAXONOMY}
    chosen, n_halluc = [], 0
    for s in (raw_list or []):
        k = norm_skill(s)
        name = lookup.get(k)
        if name is None:
            m = difflib.get_close_matches(k, list(lookup), n=1, cutoff=0.88)
            name = lookup[m[0]] if m else None
        if name is None:
            n_halluc += 1
        elif name not in chosen:
            chosen.append(name)
    for s in SKILL_TAXONOMY:
        if len(chosen) >= n: break
        if s["name"] not in chosen: chosen.append(s["name"])
    return chosen[:n], n_halluc


# ── full system prompt (used when RAG is disabled) ────────────────────────────
SYSTEM_PROMPT = f"""You are an expert curriculum analyst who tags learning content for a skills library.
You receive the extracted content of ONE learning file (slides, notebook, lab sheet, quiz, document, transcript ...)
and possibly images (slide screenshots, diagrams, scanned pages). Describe what the file actually TEACHES or ASSESSES.
Content may be in English or Arabic; always answer in English.

Return one JSON object with exactly these fields, in this order:

1. content_summary: ONE sentence on what a learner does or learns in this file and at what depth.

2. predicted_tags: 8-12 specific concepts, techniques, functions, methods or metrics the file teaches or tests,
   ordered from most to least central.
   - Each tag is a short canonical concept name (1-4 words, Title Case, standard terminology).
   - Name concrete things. A broad subject name is allowed at most once as the first tag.
   - Tag only what is covered substantively. One concept per tag; no near-duplicates.
   - Style example from an UNRELATED course (never reuse): "Docker Images", "Container Networking".

3. difficulty_level: exactly one of Beginner, Intermediate, Advanced:
   - Beginner: first exposure to the topic, introducing core vocabulary, basic syntax or single concepts.
   - Intermediate: applies known concepts in a workflow, compares methods, tunes parameters or evaluates results.
   - Advanced: builds or debugs a multi-component system end to end with research or optimisation depth.

4. predicted_skills: exactly {N_OUTPUT_SKILLS} skill names chosen from the list below, ordered most to least relevant.
   Rules:
   - Copy names EXACTLY as they appear in the list -- no paraphrasing, no invented names.
   - Rank first the broad discipline or knowledge skill of the field the content teaches.
   - Avoid tangential skills unless they are the explicit focus.

   Available skills ({len(SKILL_NAMES)} total -- pick exactly {N_OUTPUT_SKILLS}):
{SKILLS_BLOCK}

5. confidence: number 0-1. Your probability an expert reviewer agrees with tags, difficulty and skills.
   Use below 0.6 when content is thin, ambiguous or badly extracted.

6. notes: exactly 3 learning objectives, each starting with an action verb, joined with " • ".

Respond with the JSON object only."""


def build_rag_system_prompt(skill_pool: list[dict]) -> str:
    """
    RAG variant: same prompt but uses only the retrieved skill pool
    instead of the full taxonomy list.
    Called by model backends when RAG_ENABLED = True.
    """
    pool_block = "\n".join(
        f"{i+1:2}. {s['name']} -- {s['description'][:110]}"
        for i, s in enumerate(skill_pool)
    )
    return f"""You are an expert curriculum analyst who tags learning content for a skills library.
You receive the extracted content of ONE learning file (slides, notebook, lab sheet, quiz, document, transcript ...)
and possibly images (slide screenshots, diagrams, scanned pages). Describe what the file actually TEACHES or ASSESSES.
Content may be in English or Arabic; always answer in English.

Return one JSON object with exactly these fields, in this order:

1. content_summary: ONE sentence on what a learner does or learns in this file and at what depth.

2. predicted_tags: 8-12 specific concepts, techniques, functions, methods or metrics the file teaches or tests,
   ordered from most to least central.
   - Each tag is a short canonical concept name (1-4 words, Title Case, standard terminology).
   - Name concrete things. A broad subject name is allowed at most once as the first tag.
   - Tag only what is covered substantively. One concept per tag; no near-duplicates.
   - Style example from an UNRELATED course (never reuse): "Docker Images", "Container Networking".

3. difficulty_level: exactly one of Beginner, Intermediate, Advanced:
   - Beginner: first exposure to the topic, introducing core vocabulary, basic syntax or single concepts.
   - Intermediate: applies known concepts in a workflow, compares methods, tunes parameters or evaluates results.
   - Advanced: builds or debugs a multi-component system end to end with research or optimisation depth.

4. predicted_skills: exactly {N_OUTPUT_SKILLS} skill names chosen from the candidate list below,
   ordered most to least relevant.
   Rules:
   - Copy names EXACTLY as they appear in the list -- no paraphrasing, no invented names.
   - Rank first the broad discipline or knowledge skill of the field the content teaches.
   - Avoid tangential skills unless they are the explicit focus.
   - If a skill is completely unrelated to the content topic, do NOT pick it even if it appears in the candidate list.
   - Prefer skills that directly match what the content teaches over broader ones.

   Candidate skills ({len(skill_pool)} retrieved -- pick exactly {N_OUTPUT_SKILLS}):
{pool_block}

5. confidence: number 0-1. Your probability an expert reviewer agrees with tags, difficulty and skills.
   Use below 0.6 when content is thin, ambiguous or badly extracted.

6. notes: exactly 3 learning objectives, each starting with an action verb, joined with " • ".

Respond with the JSON object only."""


USER_TEMPLATE = """Content format: {fmt}
Extraction: {note}{img_note}

Extracted content:
<<<
{digest}
>>>

Return the JSON object."""


# ── difficulty refinement prompt (pass 2) ─────────────────────────────────────
DIFF_SYSTEM_PROMPT = """You assign a difficulty label to a learning file.
Read the content excerpt and return exactly one JSON object:
{"difficulty_level": "<label>", "reasoning": "<one sentence>"}

Rules:
- BEGINNER : Introduces a tool or concept from scratch; defines vocabulary; simplest examples;
  a quiz that only asks "what is X".
- ADVANCED : The learner builds a multi-component system end to end (3+ distinct technical stages).
  Reading or explaining such a system does NOT qualify -- building or running it does.
- INTERMEDIATE : Everything else. Applying known techniques, comparing methods, tuning parameters,
  evaluating results, scenario questions. Prompt engineering is always Intermediate.

Return only the JSON object."""

DIFF_USER_TEMPLATE = """File format: {fmt}

Content excerpt:
<<<
{excerpt}
>>>

Return the JSON object."""
