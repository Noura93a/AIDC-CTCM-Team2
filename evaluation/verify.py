"""
verify.py — checks all three routes and prints GREEN CHECK: PASS or FAIL.
Run with the server already up on port 8000:

    python verify.py [--server http://localhost:8000] [--file path/to/any.pdf]
"""
import argparse, sys, os, requests, tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--server", default="http://localhost:8000")
parser.add_argument("--file",   default=None,
                    help="Optional real file to use for /v1/tag check. "
                         "If omitted, a tiny synthetic text file is used.")
args = parser.parse_args()
BASE = args.server.rstrip("/")

PASS, FAIL = True, False
results = []

def check(label, ok, detail=""):
    results.append((label, ok, detail))
    status = "OK  " if ok else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))

# ── /health ───────────────────────────────────────────────────────────────────
print("\nChecking /health ...")
try:
    r = requests.get(f"{BASE}/health", timeout=10)
    body = r.json()
    check("/health returns 200", r.status_code == 200)
    check("/health has status='ok'", body.get("status") == "ok")
    check("/health lists models", isinstance(body.get("models"), list)
          and len(body["models"]) >= 1)
except Exception as e:
    check("/health reachable", False, str(e))

# ── /v1/models ────────────────────────────────────────────────────────────────
print("\nChecking /v1/models ...")
try:
    r = requests.get(f"{BASE}/v1/models", timeout=10)
    body = r.json()
    check("/v1/models returns 200", r.status_code == 200)
    check("/v1/models has object='list'", body.get("object") == "list")
    check("/v1/models data is non-empty list", isinstance(body.get("data"), list)
          and len(body["data"]) >= 1)
    check("data[0] has 'id' field", "id" in (body["data"][0] if body.get("data") else {}))
except Exception as e:
    check("/v1/models reachable", False, str(e))

# ── /v1/tag/upload (Qwen) ─────────────────────────────────────────────────────
print("\nChecking /v1/tag/upload with Qwen ...")
if args.file and os.path.exists(args.file):
    test_path = args.file
    cleanup = False
else:
    tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w")
    tmp.write("# Introduction to Pandas\n\nThis notebook covers DataFrames, Series, "
              "read_csv, groupby and basic data cleaning.")
    tmp.close()
    test_path = tmp.name
    cleanup = True

try:
    with open(test_path, "rb") as fh:
        r = requests.post(f"{BASE}/v1/tag/upload",
                          files={"file": (os.path.basename(test_path), fh)},
                          data={"model": "qwen"},
                          timeout=120)
    body = r.json() if r.status_code == 200 else {}
    check("/v1/tag/upload returns 200", r.status_code == 200,
          "" if r.status_code == 200 else r.text[:200])
    check("response has file_name",      bool(body.get("file_name")))
    check("predicted_tags non-empty",    bool(body.get("predicted_tags")))
    check("difficulty_level present",    body.get("difficulty_level") in
          ["Beginner","Intermediate","Advanced"])
    check("predicted_skills non-empty",  bool(body.get("predicted_skills")))
    check("confidence is a number",      isinstance(body.get("confidence"), (int, float)))
    check("is_valid_output is True",     body.get("is_valid_output") is True)
except Exception as e:
    check("/v1/tag/upload reachable", False, str(e))
finally:
    if cleanup: os.unlink(test_path)

# ── final verdict ─────────────────────────────────────────────────────────────
passed = sum(1 for _, ok, _ in results if ok)
total  = len(results)
print(f"\n{passed}/{total} checks passed")
if all(ok for _, ok, _ in results):
    print("GREEN CHECK: PASS")
else:
    failed = [label for label, ok, _ in results if not ok]
    print(f"GREEN CHECK: FAIL ({'; '.join(failed)})")
    sys.exit(1)
