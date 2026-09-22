"""
run_benchmark.py
================
Calls the deployed /v1/benchmark endpoint with your 12 content files,
saves per-file results and a summary report, and prints the comparison table.

Usage
-----
    # from the evaluation/ folder:
    python run_benchmark.py \
        --server http://localhost:8000 \
        --data-dir /path/to/content/files \
        --gold  /path/to/Golden-set-Reviewed.xlsx \
        --out   ./results

The script uploads files via the POST /v1/tag/upload endpoint one at a time
for each model (so it works without a public URL), then aggregates results
locally using the same scorer.py logic.
"""
from __future__ import annotations
import argparse, json, os, sys, time
import pandas as pd
import requests

# ── CLI ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--server",   default="http://localhost:8000")
parser.add_argument("--data-dir", default="./data",
                    help="Folder containing the 12 content files")
parser.add_argument("--gold",     default="./Golden-set-Reviewed.xlsx")
parser.add_argument("--out",      default="./results")
parser.add_argument("--models",   default="openai,qwen",
                    help="Comma-separated model keys to test")
args = parser.parse_args()

os.makedirs(args.out, exist_ok=True)
MODELS = [m.strip() for m in args.models.split(",")]

# ── collect files ─────────────────────────────────────────────────────────────
SKIP = {"Golden-set-Reviewed.xlsx", "hrsd_data_ai_taxonomy.csv",
        "hrsd_ai_data_skills_only.csv",
        "README_STUDENTS.md", "model_output_template.csv"}
SKIP_RE = [r"^content_tagging.*\.ipynb$", r"_results\.(csv|xlsx)$", r"^\.", r"~\$"]

import re
files = [
    f for f in sorted(os.listdir(args.data_dir))
    if os.path.isfile(os.path.join(args.data_dir, f))
    and f not in SKIP
    and not any(re.search(p, f, re.I) for p in SKIP_RE)
]
print(f"Found {len(files)} content files in {args.data_dir}")

# ── health check ──────────────────────────────────────────────────────────────
try:
    r = requests.get(f"{args.server}/health", timeout=10)
    r.raise_for_status()
    print("Server health:", r.json())
except Exception as e:
    print(f"ERROR: server not reachable at {args.server}: {e}")
    sys.exit(1)

# ── run per model ─────────────────────────────────────────────────────────────
all_rows = []

for model_key in MODELS:
    print(f"\n{'='*60}\nRunning model: {model_key}\n{'='*60}")
    model_rows = []
    wall_start = time.perf_counter()

    for fname in files:
        fpath = os.path.join(args.data_dir, fname)
        print(f"  {fname} ...", end=" ", flush=True)
        t0 = time.perf_counter()
        with open(fpath, "rb") as fh:
            resp = requests.post(
                f"{args.server}/v1/tag/upload",
                files={"file": (fname, fh)},
                data={"model": model_key},
                timeout=120,
            )
        elapsed = time.perf_counter() - t0
        if resp.status_code != 200:
            print(f"ERROR {resp.status_code}: {resp.text[:200]}")
            model_rows.append({
                "file_name": fname, "model_name": model_key,
                "error": resp.text[:200], "latency_sec": elapsed,
            })
            continue
        row = resp.json()
        row["latency_sec_client"] = round(elapsed, 3)
        model_rows.append(row)
        print(f"OK  diff={row.get('difficulty_level','')}  "
              f"tags={len(row.get('predicted_tags','').split('|'))}  "
              f"{elapsed:.1f}s")

    wall_total = time.perf_counter() - wall_start
    all_rows.extend(model_rows)

    # save per-model CSV
    pd.DataFrame(model_rows).to_csv(
        os.path.join(args.out, f"{model_key}_results.csv"), index=False)
    print(f"  Saved {len(model_rows)} rows  (wall: {wall_total:.1f}s)")

# ── save combined ─────────────────────────────────────────────────────────────
df_all = pd.DataFrame(all_rows)
df_all.to_csv(os.path.join(args.out, "all_results.csv"), index=False)

# ── gold set scoring (local) ──────────────────────────────────────────────────
TEMPLATE_COLS = ["file_name","model_name","content_type","predicted_tags",
                 "difficulty_level","predicted_skills","confidence","notes"]

if os.path.exists(args.gold):
    gold_df = pd.read_excel(args.gold)
    def fkey(n): return re.sub(r"[^a-z0-9.]","", os.path.basename(str(n)).lower())
    gold_map = {fkey(r["file_name"]): r for _, r in gold_df.iterrows()}

    def jaccard(a, b):
        a = set(x.strip().lower() for x in str(a).split("|") if x.strip())
        b = set(x.strip().lower() for x in str(b).split("|") if x.strip())
        if not a and not b: return None
        return round(len(a & b) / len(a | b), 3)

    def skill_recall(pred_str, gold_str):
        pred = set(x.strip().lower() for x in str(pred_str).split("|") if x.strip())
        gold = set(x.strip().lower() for x in str(gold_str).split("|") if x.strip())
        if not gold: return None
        return round(len(pred & gold) / len(gold), 3)

    scored = []
    for _, row in df_all.iterrows():
        g = gold_map.get(fkey(row.get("file_name","")))
        r = dict(row)
        if g is not None:
            r["diff_correct"]    = (str(row.get("difficulty_level","")).lower()
                                    == str(g.get("difficulty_level","")).strip().lower())
            r["tag_jaccard"]     = jaccard(row.get("predicted_tags",""),
                                           g.get("predicted_tags",""))
            r["skill_jaccard"]   = jaccard(row.get("predicted_skills",""),
                                           g.get("predicted_skills",""))
            r["skill_recall"]    = skill_recall(row.get("predicted_skills",""),
                                                g.get("predicted_skills",""))
        scored.append(r)

    df_scored = pd.DataFrame(scored)

    # ── per-model aggregate ───────────────────────────────────────────────────
    def pct(series): return round(series.mean() * 100, 1) if series.notna().any() else None
    def avg(series): return round(series.mean(), 4)    if series.notna().any() else None

    agg_rows = []
    VALID_DIFF = ["Beginner","Intermediate","Advanced"]
    for model_name, grp in df_scored.groupby("model_name"):
        n = len(grp)
        diff_acc   = pct(grp["diff_correct"])   if "diff_correct"  in grp else None
        tag_strict = pct(grp["tag_jaccard"])     if "tag_jaccard"   in grp else None
        sk_jac     = pct(grp["skill_jaccard"])   if "skill_jaccard" in grp else None
        sk_rec     = pct(grp["skill_recall"])    if "skill_recall"  in grp else None
        tag_class  = (round((diff_acc + tag_strict)/2, 1)
                      if diff_acc is not None and tag_strict is not None else None)
        valid_pct  = round(100 * grp["is_valid_output"].sum() / n, 1) if "is_valid_output" in grp else None
        avg_lat    = avg(grp["latency_sec"])     if "latency_sec"   in grp else None
        total_tok  = int(grp["total_tokens"].sum()) if "total_tokens" in grp else 0
        total_cost = round(grp["est_cost_usd"].sum(), 6) if "est_cost_usd" in grp else 0.0
        wall       = grp["latency_sec"].sum()    if "latency_sec"   in grp else 0.0
        items_hr   = round(3600 / max(0.001, wall / max(1, n)), 1)
        agg_rows.append({
            "model_name":                          model_name,
            "n_items":                             n,
            # ── 7 required metrics ──────────────────────────────────────────
            "tagging_classification_accuracy_pct": tag_class,
            "skill_mapping_accuracy_pct":          sk_jac,
            "retrieval_quality":                   "N/A (full list in prompt)",
            "structured_output_validity_pct":      valid_pct,
            "avg_latency_sec":                     avg_lat,
            "total_tokens":                        total_tok,
            "est_total_cost_usd":                  total_cost,
            "est_items_per_hour":                  items_hr,
            # ── diagnostics ─────────────────────────────────────────────────
            "difficulty_accuracy_pct":             diff_acc,
            "tag_overlap_strict_pct":              tag_strict,
            "skill_recall_at_n_pct":               sk_rec,
        })

    summary_df = pd.DataFrame(agg_rows)

    # ── print performance & accuracy summary ──────────────────────────────────
    metric_cols = ["model_name","n_items",
                   "tagging_classification_accuracy_pct",
                   "skill_mapping_accuracy_pct",
                   "retrieval_quality",
                   "structured_output_validity_pct",
                   "avg_latency_sec",
                   "total_tokens","est_total_cost_usd","est_items_per_hour"]
    diag_cols   = ["model_name","difficulty_accuracy_pct",
                   "tag_overlap_strict_pct","skill_recall_at_n_pct"]

    print(f"\n{'='*100}")
    print("PERFORMANCE & ACCURACY SUMMARY")
    print(f"{'='*100}")
    print(summary_df[[c for c in metric_cols if c in summary_df.columns]].to_string(index=False))
    print(f"\nDiagnostics:")
    print(summary_df[[c for c in diag_cols if c in summary_df.columns]].to_string(index=False))

    # ── deployment readiness check ─────────────────────────────────────────
    THRESHOLDS = {"structured_output_validity_pct": 95.0,
                  "avg_latency_sec":                10.0,
                  "skill_mapping_accuracy_pct":     25.0}
    for _, agg in summary_df.iterrows():
        mid = agg["model_name"]
        print(f"\n{'='*90}")
        print(f"DEPLOYMENT READINESS CHECK -- {mid}")
        print(f"{'='*90}")
        def chk(k, op, thr, label):
            v = agg.get(k)
            if v is None or not isinstance(v, (int, float)):
                print(f"  [N/A ] {label}: {v}"); return
            ok = (v >= thr) if op == ">=" else (v <= thr)
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {v} (need {op} {thr})")
        chk("structured_output_validity_pct", ">=", 95.0,  "Structured-output validity (%)")
        chk("avg_latency_sec",               "<=", 10.0,  "Average latency (s)")
        chk("skill_mapping_accuracy_pct",    ">=", 25.0,  "Skill-mapping accuracy / Jaccard (%)")
        print(f"  [INFO] Tagging/classification accuracy: {agg.get('tagging_classification_accuracy_pct')}%")
        print(f"  [INFO] Difficulty accuracy: {agg.get('difficulty_accuracy_pct')}%  |  "
              f"tag overlap strict: {agg.get('tag_overlap_strict_pct')}%")
        print(f"  [INFO] Skill recall@4: {agg.get('skill_recall_at_n_pct')}%  |  "
              f"retrieval quality: {agg.get('retrieval_quality')}")
        print(f"  [INFO] Token usage: {agg.get('total_tokens')} tokens  |  "
              f"cost: ${agg.get('est_total_cost_usd')}  |  "
              f"throughput: {agg.get('est_items_per_hour')} files/hr")

    # ── per-file comparison table ─────────────────────────────────────────────
    print(f"\n{'='*90}")
    print("PER-FILE RESULTS")
    print(f"{'='*90}")
    per_file_cols = ["file_name","model_name","difficulty_level",
                     "diff_correct","tag_jaccard","skill_jaccard","skill_recall",
                     "confidence","is_valid_output","latency_sec"]
    print(df_scored[[c for c in per_file_cols if c in df_scored.columns]].to_string(index=False))

    # ── save ──────────────────────────────────────────────────────────────────
    df_scored.to_csv(os.path.join(args.out, "scored_results.csv"), index=False)
    summary_df.to_csv(os.path.join(args.out, "benchmark_summary.csv"), index=False)
    summary_df.to_excel(os.path.join(args.out, "benchmark_summary.xlsx"), index=False, engine="openpyxl")
    print(f"\nAll results saved to {args.out}/")

else:
    print(f"\nGold set not found at {args.gold} — skipping accuracy scoring.")
    print(f"Results saved to {args.out}/all_results.csv")
