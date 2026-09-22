# API request examples

All examples assume the server is running on `localhost:8000`.

---

## GET /health
```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```
Expected:
```json
{"status": "ok", "models": ["gpt-4o-mini", "Qwen/Qwen2.5-VL-3B-Instruct-AWQ"]}
```

---

## GET /v1/models
```bash
curl -s http://localhost:8000/v1/models | python3 -m json.tool
```
Expected:
```json
{
  "object": "list",
  "data": [
    {"id": "gpt-4o-mini", "object": "model", "owned_by": "content-tagging-service"},
    {"id": "Qwen/Qwen2.5-VL-3B-Instruct-AWQ", "object": "model", "owned_by": "content-tagging-service"}
  ]
}
```

---

## POST /v1/tag/upload  (Qwen, file upload)
```bash
curl -s http://localhost:8000/v1/tag/upload \
  -F "file=@/path/to/Lecture-Pandas-Basics.ipynb" \
  -F "model=qwen" | python3 -m json.tool
```
Required in response: `predicted_tags` non-empty, `difficulty_level` in
[Beginner, Intermediate, Advanced], `predicted_skills` non-empty,
`confidence` a number, `is_valid_output` true.

---

## POST /v1/tag/upload  (OpenAI)
```bash
curl -s http://localhost:8000/v1/tag/upload \
  -F "file=@/path/to/Decision-Trees-Revised.pptx" \
  -F "model=openai" | python3 -m json.tool
```

---

## POST /v1/tag  (URL-based)
```bash
curl -s http://localhost:8000/v1/tag \
  -H "Content-Type: application/json" \
  -d '{
    "file_url": "https://example.com/myfile.pdf",
    "filename": "myfile.pdf",
    "model": "qwen"
  }' | python3 -m json.tool
```

---

## POST /v1/benchmark  (both models, URL-based)
```bash
curl -s http://localhost:8000/v1/benchmark \
  -H "Content-Type: application/json" \
  -d '{
    "file_urls": ["https://example.com/file1.pptx", "https://example.com/file2.ipynb"],
    "filenames": ["Decision-Trees.pptx", "Pandas-Basics.ipynb"]
  }' | python3 -m json.tool
```
Returns `BenchmarkReport` with `results[]`, `aggregates[]`, and `winner`.

---

## Run the full local benchmark (with file upload per file)
```bash
cd evaluation/
python run_benchmark.py \
  --server http://localhost:8000 \
  --data-dir /path/to/your/12/files \
  --gold     /path/to/Golden-set-Reviewed.xlsx \
  --out      ./results \
  --models   openai,qwen
```

## Green check
```bash
python verify.py --server http://localhost:8000
```
