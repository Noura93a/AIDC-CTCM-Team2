"""
extractor.py — universal content extraction (text + images) for any file type.
Ported directly from the working Colab notebooks.
"""
from __future__ import annotations
import os, re, base64, io, math, zipfile, tempfile, subprocess
import pandas as pd
from PIL import Image, ImageOps
from config import (
    INCLUDE_IMAGES, MAX_IMAGES_PER_FILE, MAX_IMAGE_DIM, VISUAL_SLIDE_MAX_WORDS,
    ENABLE_OCR, OCR_LANGS, OCR_MAX_PAGES, SCANNED_PDF_CHARS_PER_PAGE,
    MAX_ROWS_PER_SHEET, ZIP_MAX_MEMBERS, MAX_PROMPT_CHARS,
)

# ── extension sets ────────────────────────────────────────────────────────────
PPTX_EXTS    = {"pptx","pptm","ppsx","potx"}
LEGACY_PPT   = {"ppt","pps","pot","odp","key"}
DOCX_EXTS    = {"docx","docm","dotx"}
LEGACY_DOC   = {"doc","odt","rtf","wpd","pages"}
SHEET_EXTS   = {"xlsx","xlsm","xltx","xls","ods"}
DELIM_EXTS   = {"csv","tsv","tab"}
PDF_EXTS     = {"pdf","epub","xps"}
HTML_EXTS    = {"html","htm","xhtml"}
IMAGE_EXTS   = {"png","jpg","jpeg","webp","bmp","gif","tif","tiff"}
AV_EXTS      = {"mp3","wav","m4a","aac","flac","ogg","mp4","mov","mkv","webm","avi"}
ARCHIVE_EXTS = {"zip"}
CODE_EXTS    = {"py","sql","r","js","ts","java","scala","sh","bash","c","cpp","h","cs",
                "go","rb","jl","m","kt","swift","php","rs","ps1","dax","sas","do","hql","psql"}
TEXT_EXTS    = {"md","markdown","txt","rst","tex","json","jsonl","yaml","yml","toml","ini",
                "cfg","xml","log","srt","vtt","qmd","rmd","adoc","org"}
DOC_LIKE_TYPES = {"md","markdown","ipynb","docx","docm","doc","odt","rtf","html","htm","xhtml",
                  "txt","rst","qmd","rmd","xlsx","xlsm","xls","ods","csv","tsv","zip"}

class UnsupportedFileType(Exception):
    pass

# ── helpers ───────────────────────────────────────────────────────────────────
def pick_evenly(items, n):
    items = list(items)
    if n <= 0: return []
    if len(items) <= n: return items
    if n == 1: return [items[len(items)//2]]
    return [items[round(i*(len(items)-1)/(n-1))] for i in range(n)]

def resize_image(img, max_dim=MAX_IMAGE_DIM):
    if img.mode in ("RGBA","LA","P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255,255,255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, max_dim / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1,int(w*scale)), max(1,int(h*scale))), Image.LANCZOS)
    return img

def ocr_image(img):
    if not ENABLE_OCR: return ""
    try:
        import pytesseract
    except ImportError:
        return ""
    for langs in (OCR_LANGS, "eng"):
        try:
            return pytesseract.image_to_string(img, lang=langs).strip()
        except Exception:
            continue
    return ""

_B64_RE = re.compile(r"[A-Za-z0-9+/=]{200,}")

def clean_text(text):
    text = _B64_RE.sub("[binary data removed]", text or "")
    kept = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            kept.append(""); continue
        symbols = sum(1 for ch in s if not ch.isalnum() and not ch.isspace())
        if len(s) > 15 and symbols/len(s) > 0.5: continue
        kept.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()

def extract_outline(text, content_type):
    out, in_fence = [], False
    md_headings = content_type in DOC_LIKE_TYPES
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("```"): in_fence = not in_fence; continue
        if in_fence: continue
        if s.startswith("--- Slide") or s.startswith("--- Page"):
            if ":" in s: out.append(s.strip("- ").strip())
        elif md_headings and re.match(r"^#{1,6}\s+\S", s):
            out.append(s[:140])
    seen, uniq = set(), []
    for o in out:
        k = o.lower()
        if k not in seen: seen.add(k); uniq.append(o)
    return uniq

def build_digest(text, content_type, budget=MAX_PROMPT_CHARS, window=900):
    if not text.strip():
        return "(no extractable text -- rely on the attached image(s))", "no text layer"
    if len(text) <= budget:
        return text, "full content"
    outline = extract_outline(text, content_type)
    outline_budget = int(budget * 0.35)
    while outline and len("\n".join(outline)) > outline_budget:
        outline = outline[::2]
    outline_str = "OUTLINE (section headings / slide titles, in order):\n" + "\n".join(outline) if outline else ""
    body_budget = budget - len(outline_str) - 80
    n_chunks = max(1, min(8, body_budget // window))
    step = max(1, (len(text)-window)//(n_chunks-1)) if n_chunks > 1 else len(text)
    chunks = []
    for i in range(n_chunks):
        start = min(i*step, len(text)-window)
        chunks.append(text[start:start+window].strip())
    chunks_str = "\n[...]\n".join(chunks)
    body_str = f"EXCERPTS (evenly spaced from start to end):\n{chunks_str}"
    digest = (outline_str + "\n\n" + body_str).strip() if outline_str else body_str
    return digest, f"summarised ({len(text):,} chars → {len(digest):,})"

# ── extractors ────────────────────────────────────────────────────────────────
def _extract_pptx(path):
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    prs = Presentation(path)
    texts, images = [], []
    for slide_num, slide in enumerate(prs.slides, 1):
        slide_texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    t = " ".join(r.text for r in para.runs).strip()
                    if t: slide_texts.append(t)
            if INCLUDE_IMAGES and shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    img = Image.open(io.BytesIO(shape.image.blob))
                    images.append(resize_image(img))
                except Exception:
                    pass
        word_count = sum(len(t.split()) for t in slide_texts)
        slide_label = f"--- Slide {slide_num}: {slide_texts[0][:60] if slide_texts else ''} ---"
        if word_count <= VISUAL_SLIDE_MAX_WORDS and INCLUDE_IMAGES:
            try:
                import PIL.ImageDraw
                img = Image.new("RGB", (800,450), (255,255,255))
                for i, t in enumerate(slide_texts[:3]):
                    PIL.ImageDraw.Draw(img).text((20,20+i*40), t[:80], fill=(0,0,0))
                images.append(resize_image(img))
            except Exception:
                pass
            texts.append(slide_label + " [visual slide]")
        else:
            texts.append(slide_label)
            texts.extend(slide_texts)
    return clean_text("\n".join(texts)), images[:MAX_IMAGES_PER_FILE]

def _extract_docx(path):
    from docx import Document
    doc = Document(path)
    texts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return clean_text("\n".join(texts)), []

def _extract_sheet(path, ext):
    try:
        sheets = pd.read_excel(path, sheet_name=None, nrows=MAX_ROWS_PER_SHEET)
    except Exception:
        sheets = {"Sheet1": pd.read_csv(path, nrows=MAX_ROWS_PER_SHEET)}
    parts = []
    for name, df in sheets.items():
        df = df.fillna("").astype(str)
        parts.append(f"## Sheet: {name} ({df.shape[0]} rows x {df.shape[1]} cols)")
        parts.append(df.to_string(index=False, max_rows=MAX_ROWS_PER_SHEET))
    return clean_text("\n\n".join(parts)), []

def _extract_pdf(path):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open(path)
    texts, images = [], []
    for page_num, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            texts.append(f"--- Page {page_num+1} ---\n{text}")
        elif INCLUDE_IMAGES and page_num < OCR_MAX_PAGES:
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = ocr_image(img)
            if ocr_text:
                texts.append(f"--- Page {page_num+1} (OCR) ---\n{ocr_text}")
            if len(images) < MAX_IMAGES_PER_FILE:
                images.append(resize_image(img))
    return clean_text("\n\n".join(texts)), images

def _extract_ipynb(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        nb = __import__("json").load(f)
    parts = []
    for cell in nb.get("cells", []):
        ct = cell.get("cell_type","")
        src = "".join(cell.get("source",""))
        if not src.strip(): continue
        if ct == "markdown":
            parts.append(src)
        elif ct == "code":
            parts.append(f"```python\n{src}\n```")
    return clean_text("\n\n".join(parts)), []

def _extract_text(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return clean_text(f.read()), []

def _extract_html(path):
    from bs4 import BeautifulSoup
    with open(path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")
    for tag in soup(["script","style"]): tag.decompose()
    return clean_text(soup.get_text("\n")), []

def _libreoffice_convert(path, fmt="pptx"):
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["soffice","--headless","--convert-to",fmt,"--outdir",tmpdir,path],
                       capture_output=True, timeout=60)
        candidates = [os.path.join(tmpdir,f) for f in os.listdir(tmpdir)]
        if candidates:
            out = candidates[0]
            if fmt == "pptx": return _extract_pptx(out)
            return _extract_docx(out)
    return "", []

def _extract_zip(path):
    parts, images = [], []
    with zipfile.ZipFile(path) as zf:
        members = [m for m in zf.namelist() if not m.startswith("__MACOSX") and not m.endswith("/")][:ZIP_MAX_MEMBERS]
        with tempfile.TemporaryDirectory() as tmpdir:
            for m in members:
                zf.extract(m, tmpdir)
                try:
                    t, imgs = extract_content(os.path.join(tmpdir, m))
                    if t: parts.append(f"--- {os.path.basename(m)} ---\n{t}")
                    images.extend(imgs)
                except Exception:
                    pass
    return clean_text("\n\n".join(parts)), images[:MAX_IMAGES_PER_FILE]

# ── dispatcher ────────────────────────────────────────────────────────────────
def extract_content(path: str) -> dict:
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "unknown"
    text, images = "", []
    try:
        if ext in PPTX_EXTS:                text, images = _extract_pptx(path)
        elif ext in LEGACY_PPT:             text, images = _libreoffice_convert(path, "pptx")
        elif ext in DOCX_EXTS:             text, images = _extract_docx(path)
        elif ext in LEGACY_DOC:            text, images = _libreoffice_convert(path, "docx")
        elif ext in SHEET_EXTS|DELIM_EXTS: text, images = _extract_sheet(path, ext)
        elif ext in PDF_EXTS:              text, images = _extract_pdf(path)
        elif ext == "ipynb":               text, images = _extract_ipynb(path)
        elif ext in HTML_EXTS:             text, images = _extract_html(path)
        elif ext in TEXT_EXTS|CODE_EXTS:   text, images = _extract_text(path)
        elif ext in IMAGE_EXTS:
            img = resize_image(Image.open(path))
            text = ocr_image(img)
            images = [img] if INCLUDE_IMAGES else []
        elif ext in ARCHIVE_EXTS:          text, images = _extract_zip(path)
        else:
            raise UnsupportedFileType(f".{ext}")
    except UnsupportedFileType:
        raise
    except Exception as e:
        raise RuntimeError(f"extraction failed for {os.path.basename(path)}: {e}") from e
    return {"text": text, "images": images[:MAX_IMAGES_PER_FILE], "content_type": ext, "meta": {}}

def release_extraction_models():
    pass  # placeholder for OCR/whisper model cleanup if needed
