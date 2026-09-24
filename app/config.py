"""
config.py — all tuneable constants in one place.
Set OPENAI_API_KEY and SKILLS_CSV_PATH via environment variables or .env.
"""
import os

# ── models ────────────────────────────────────────────────────────────────────
OPENAI_MODEL   = os.getenv("OPENAI_MODEL",   "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

QWEN_MODEL_ID  = os.getenv("QWEN_MODEL_ID",  "Qwen/Qwen2.5-VL-3B-Instruct-AWQ")
QWEN_QUANT     = "awq"
QWEN_VISION    = True

# ── extraction ────────────────────────────────────────────────────────────────
INCLUDE_IMAGES          = True
MAX_IMAGES_PER_FILE     = 2
MAX_IMAGE_DIM           = 768
VISUAL_SLIDE_MAX_WORDS  = 15
ENABLE_OCR              = True
OCR_LANGS               = "eng+ara"
OCR_MAX_PAGES           = 12
SCANNED_PDF_CHARS_PER_PAGE = 80
MAX_ROWS_PER_SHEET      = 200
ZIP_MAX_MEMBERS         = 15

# ── prompt ────────────────────────────────────────────────────────────────────
MAX_PROMPT_CHARS  = 6000
MAX_TAGS          = 12
MAX_NEW_TOKENS    = 900
N_OUTPUT_SKILLS   = 4

# ── skills taxonomy ───────────────────────────────────────────────────────────
SKILLS_CSV_PATH = os.getenv(
    "SKILLS_CSV_PATH",
    os.path.join(os.path.dirname(__file__), "../data/hrsd_data_ai_taxonomy.csv")
)

# ── RAG skill retrieval ───────────────────────────────────────────────────────
RAG_ENABLED        = True
RAG_EMBED_MODEL_ID = "BAAI/bge-m3"
RAG_POOL_K         = 15
RAG_CHUNK_CHARS    = 1200
RAG_CHUNK_OVERLAP  = 200
RAG_TAG_WEIGHT     = 1.5
RAG_CONTENT_WEIGHT = 1.0
RAG_RRF_K          = 20

# ── vLLM (Qwen) ───────────────────────────────────────────────────────────────
MAX_MODEL_LEN          = 8192
GPU_MEM_UTIL           = 0.12
ENFORCE_EAGER          = True
USE_STRUCTURED_OUTPUTS = False
SINGLE_REQUEST_TEST_N  = 3

# ── scoring ───────────────────────────────────────────────────────────────────
GPU_COST_PER_HOUR_USD     = 0.35
OPENAI_INPUT_COST_PER_1K  = 0.000150
OPENAI_OUTPUT_COST_PER_1K = 0.000600
VALID_DIFFICULTY          = ["Beginner", "Intermediate", "Advanced"]
COMPUTE_SEMANTIC_METRICS  = True
SCORING_EMBED_MODEL_ID    = "BAAI/bge-m3"
TAG_SIM_THRESHOLD         = 0.72

# ── misc ──────────────────────────────────────────────────────────────────────
DIFF_EXCERPT_CHARS = 1500
REPETITION_PENALTY = 1.05
