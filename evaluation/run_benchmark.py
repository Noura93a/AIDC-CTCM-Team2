"""
run_benchmark.py
================
Calls the deployed /v1/tag/upload endpoint with your content files,
saves per-file results and a summary report, and prints the comparison table.

Metrics reported:
  7 required: tagging accuracy, skill mapping, retrieval quality,
              structured validity, latency, tokens/cost, scalability
  Extra:      tag semantic F1, tag precision, tag recall,
              skill precision, tokens/sec, cost per 1000 files

Usage
-----
    python evaluation/run_benchmark.py \
        --server   http://localhost:8000 \
        --data-dir ./data \
        --gold     ./data/Golden-set-Reviewed.xlsx \
        --models   openai,qwen \
        --out      ./results
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

import pandas as pd
import requests


# ── CLI ──────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument("--server", default="http://localhost:8000")
parser.add_argument("--data-dir", default="./data")
parser.add_argument("--gold", default="./data/Golden-set-Reviewed.xlsx")
parser.add_argument("--out", default="./results")
parser.add_argument(
    "--models",
    default="openai,qwen",
    help="Comma-separated model keys: openai,qwen",
)
args = parser.parse_args()

os.makedirs(args.out, exist_ok=True)
MODELS = [m.strip() for m in args.models.split(",") if m.strip()]


# ── collect files ─────────────────────────────────────────────────────────────

SKIP = {
    "Golden-set-Reviewed.xlsx",
    "hrsd_data_ai_taxonomy.csv",
    "hrsd_ai_data_skills_only.csv",
    "README_STUDENTS.md",
    "model_output_template.csv",
}

SKIP_RE = [
    r"^content_tagging.*\.ipynb$",
    r"_results\.(csv|xlsx)$",
    r"^\.",
    r"~\$",
]

files = [
    f
    for f in sorted(os.listdir(args.data_dir))
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
except requests.exceptions.RequestException as e:
    print(f"ERROR: server not reachable at {args.server}: {e}")
    sys.exit(1)


# ── run per model ─────────────────────────────────────────────────────────────

all_rows = []

for model_key in MODELS:
    print(f"\n{'=' * 60}\nRunning model: {model_key}\n{'=' * 60}")
    model_rows = []
    wall_start = time.perf_counter()

    for fname in files:
        fpath = os.path.join(args.data_dir, fname)
        print(f"  {fname[:55]} ...", end=" ", flush=True)

        t0 = time.perf_counter()

        try:
            with open(fpath, "rb") as fh:
                resp = requests.post(
                    f"{args.server}/v1/tag/upload",
                    files={"file": (fname, fh)},
                    data={"model": model_key},
                    timeout=600,
                )

            elapsed = time.perf_counter() - t0

        except requests.exceptions.RequestException as e:
            elapsed = time.perf_counter() - t0

            print(f"FAILED: {e}")

            model_rows.append(
                {
                    "file_name": fname,
                    "model_name": model_key,
                    "error": str(e),
                    "latency_sec_client": round(elapsed, 3),
                }
            )
            continue

        if resp.status_code != 200:
            print(f"ERROR {resp.status_code}: {resp.text[:200]}")

            model_rows.append(
                {
                    "file_name": fname,
                    "model_name": model_key,
                    "error": resp.text[:200],
                    "latency_sec_client": round(elapsed, 3),
                }
            )
            continue

        try:
            row = resp.json()
        except ValueError as e:
            print(f"FAILED: invalid JSON response: {e}")
            model_rows.append(
                {
                    "file_name": fname,
                    "model_name": model_key,
                    "error": f"invalid JSON response: {e}",
                    "latency_sec_client": round(elapsed, 3),
                }
            )
            continue

        row["latency_sec_client"] = round(elapsed, 3)
        model_rows.append(row)

        print(
            f"OK  diff={row.get('difficulty_level', '')}  "
            f"tags={len(str(row.get('predicted_tags', '')).split('|'))}  "
            f"{elapsed:.1f}s"
        )

    wall_total = time.perf_counter() - wall_start
    all_rows.extend(model_rows)

    pd.DataFrame(model_rows).to_csv(
        os.path.join(args.out, f"{model_key}_results.csv"),
        index=False,
    )
    print(f"  Saved {len(model_rows)} rows  (wall: {wall_total:.1f}s)")


# ── save combined ─────────────────────────────────────────────────────────────

df_all = pd.DataFrame(all_rows)
df_all.to_csv(os.path.join(args.out, "all_results.csv"), index=False)


# ── gold set scoring (local) ──────────────────────────────────────────────────

if os.path.exists(args.gold):
    gold_df = pd.read_excel(args.gold)

    def fkey(n):
        return re.sub(
            r"[^a-z0-9.]",
            "",
            os.path.basename(str(n)).lower(),
        )

    gold_map = {fkey(r["file_name"]): r for _, r in gold_df.iterrows()}

    # ── metric helpers ────────────────────────────────────────────────────────

    def split_pipe(v):
        if pd.isna(v):
            return []
        return [
            x.strip().lower()
            for x in str(v).split("|")
            if x.strip()
        ]

    def jaccard(a, b):
        a, b = set(split_pipe(a)), set(split_pipe(b))
        if not a and not b:
            return None
        return round(len(a & b) / len(a | b), 3)

    def precision_fn(pred_str, gold_str):
        p = set(split_pipe(pred_str))
        g = set(split_pipe(gold_str))
        if not p:
            return None
        return round(len(p & g) / len(p), 3)

    def recall_fn(pred_str, gold_str):
        p = set(split_pipe(pred_str))
        g = set(split_pipe(gold_str))
        if not g:
            return None
        return round(len(p & g) / len(g), 3)

    # ── score per file ────────────────────────────────────────────────────────

    scored = []

    for _, row in df_all.iterrows():
        g = gold_map.get(fkey(row.get("file_name", "")))
        r = dict(row)

        if g is not None:
            r["diff_correct"] = (
                str(row.get("difficulty_level", "")).lower()
                == str(g.get("difficulty_level", "")).strip().lower()
            )

            r["tag_jaccard"] = jaccard(
                row.get("predicted_tags", ""),
                g.get("predicted_tags", ""),
            )
            r["tag_precision"] = precision_fn(
                row.get("predicted_tags", ""),
                g.get("predicted_tags", ""),
            )
            r["tag_recall"] = recall_fn(
                row.get("predicted_tags", ""),
                g.get("predicted_tags", ""),
            )
            r["skill_jaccard"] = jaccard(
                row.get("predicted_skills", ""),
                g.get("predicted_skills", ""),
            )
            r["skill_recall"] = recall_fn(
                row.get("predicted_skills", ""),
                g.get("predicted_skills", ""),
            )
            r["skill_precision"] = precision_fn(
                row.get("predicted_skills", ""),
                g.get("predicted_skills", ""),
            )

        scored.append(r)

    df_scored = pd.DataFrame(scored)

    # ── aggregate per model ───────────────────────────────────────────────────

    def pct(series):
        numeric = pd.to_numeric(series, errors="coerce")
        return round(numeric.mean() * 100, 1) if numeric.notna().any() else None

    def avg(series):
        numeric = pd.to_numeric(series, errors="coerce")
        return round(numeric.mean(), 4) if numeric.notna().any() else None

    agg_rows = []

    for model_name, grp in df_scored.groupby("model_name"):
        n = len(grp)

        diff_acc = pct(grp["diff_correct"]) if "diff_correct" in grp else None
        tag_strict = pct(grp["tag_jaccard"]) if "tag_jaccard" in grp else None
        tag_prec = pct(grp["tag_precision"]) if "tag_precision" in grp else None
        tag_rec = pct(grp["tag_recall"]) if "tag_recall" in grp else None
        tag_semf1 = pct(grp["tag_semantic_f1"]) if "tag_semantic_f1" in grp else None
        sk_jac = pct(grp["skill_jaccard"]) if "skill_jaccard" in grp else None
        sk_rec = pct(grp["skill_recall"]) if "skill_recall" in grp else None
        sk_prec = pct(grp["skill_precision"]) if "skill_precision" in grp else None
        pool_rec = pct(grp["pool_recall"]) if "pool_recall" in grp else None

        tag_class = (
            round((diff_acc + tag_strict) / 2, 1)
            if diff_acc is not None and tag_strict is not None
            else None
        )

        valid_pct = (
            round(
                100
                * pd.to_numeric(
                    grp["is_valid_output"],
                    errors="coerce",
                ).fillna(0).sum()
                / n,
                1,
            )
            if "is_valid_output" in grp
            else None
        )

        # End-to-end latency measured by the benchmark client.
        avg_lat = (
            avg(grp["latency_sec_client"])
            if "latency_sec_client" in grp
            else None
        )

        avg_tps = (
            avg(grp["tokens_per_sec"])
            if "tokens_per_sec" in grp
            else None
        )

        total_tok = (
            int(pd.to_numeric(grp["total_tokens"], errors="coerce").fillna(0).sum())
            if "total_tokens" in grp
            else 0
        )

        total_cost = (
            round(
                pd.to_numeric(
                    grp["est_cost_usd"],
                    errors="coerce",
                ).fillna(0).sum(),
                6,
            )
            if "est_cost_usd" in grp
            else 0.0
        )

        # Sequential end-to-end throughput based on client-observed latency.
        wall = (
            pd.to_numeric(
                grp["latency_sec_client"],
                errors="coerce",
            ).fillna(0).sum()
            if "latency_sec_client" in grp
            else 0.0
        )

        items_hr = round(
            3600 / max(0.001, wall / max(1, n)),
            1,
        )

        cost_1k = round(total_cost / max(1, n) * 1000, 4)

        ret_qual = (
            f"{pool_rec}% pool recall"
            if pool_rec is not None
            else "N/A (full list in prompt)"
        )

        agg_rows.append(
            {
                "model_name": model_name,
                "n_items": n,
                # ── 7 required ───────────────────────────────────────────────
                "tagging_classification_accuracy_pct": tag_class,
                "skill_mapping_accuracy_pct": sk_jac,
                "retrieval_quality": ret_qual,
                "structured_output_validity_pct": valid_pct,
                "avg_latency_sec": avg_lat,
                "total_tokens": total_tok,
                "est_total_cost_usd": total_cost,
                "est_items_per_hour": items_hr,
                # ── extra metrics ────────────────────────────────────────────
                "tag_semantic_f1_pct": tag_semf1,
                "tag_precision_pct": tag_prec,
                "tag_recall_pct": tag_rec,
                "skill_precision_pct": sk_prec,
                "avg_tokens_per_sec": avg_tps,
                "est_cost_per_1000_files_usd": cost_1k,
                # ── diagnostics ─────────────────────────────────────────────
                "difficulty_accuracy_pct": diff_acc,
                "tag_overlap_strict_pct": tag_strict,
                "skill_recall_at_n_pct": sk_rec,
            }
        )

    summary_df = pd.DataFrame(agg_rows)

    # ── PERFORMANCE & ACCURACY SUMMARY ───────────────────────────────────────

    required_cols = [
        "model_name",
        "n_items",
        "tagging_classification_accuracy_pct",
        "skill_mapping_accuracy_pct",
        "retrieval_quality",
        "structured_output_validity_pct",
        "avg_latency_sec",
        "total_tokens",
        "est_total_cost_usd",
        "est_items_per_hour",
    ]

    extra_cols = [
        "model_name",
        "tag_semantic_f1_pct",
        "tag_precision_pct",
        "tag_recall_pct",
        "skill_precision_pct",
        "avg_tokens_per_sec",
        "est_cost_per_1000_files_usd",
    ]

    diag_cols = [
        "model_name",
        "difficulty_accuracy_pct",
        "tag_overlap_strict_pct",
        "skill_recall_at_n_pct",
    ]

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)

    print(f"\n{'=' * 110}")
    print("PERFORMANCE & ACCURACY SUMMARY  (7 required metrics)")
    print(f"{'=' * 110}")
    print(
        summary_df[
            [c for c in required_cols if c in summary_df.columns]
        ].to_string(index=False)
    )

    print("\nExtra metrics:")
    print(
        summary_df[
            [c for c in extra_cols if c in summary_df.columns]
        ].to_string(index=False)
    )

    print("\nDiagnostics:")
    print(
        summary_df[
            [c for c in diag_cols if c in summary_df.columns]
        ].to_string(index=False)
    )

    # ── DEPLOYMENT READINESS CHECK ────────────────────────────────────────────

    for _, agg in summary_df.iterrows():
        mid = agg["model_name"]

        print(f"\n{'=' * 90}")
        print(f"DEPLOYMENT READINESS CHECK -- {mid}")
        print(f"{'=' * 90}")

        def chk(k, op, thr, label):
            v = agg.get(k)
            if v is None or not isinstance(v, (int, float)):
                print(f"  [N/A ] {label}: {v}")
                return

            ok = (v >= thr) if op == ">=" else (v <= thr)

            print(
                f"  [{'PASS' if ok else 'FAIL'}] {label}: {v} "
                f"(need {op} {thr})"
            )

        chk(
            "structured_output_validity_pct",
            ">=",
            95.0,
            "Structured-output validity (%)",
        )
        chk(
            "avg_latency_sec",
            "<=",
            10.0,
            "Average latency (s)",
        )
        chk(
            "skill_mapping_accuracy_pct",
            ">=",
            25.0,
            "Skill-mapping accuracy / Jaccard (%)",
        )

        print(
            "  [INFO] Tagging/classification accuracy: "
            f"{agg.get('tagging_classification_accuracy_pct')}%"
        )
        print(
            "  [INFO] Difficulty accuracy: "
            f"{agg.get('difficulty_accuracy_pct')}%  |  "
            f"tag overlap strict: {agg.get('tag_overlap_strict_pct')}%"
        )
        print(
            f"  [INFO] Tag precision: {agg.get('tag_precision_pct')}%  |  "
            f"tag recall: {agg.get('tag_recall_pct')}%  |  "
            f"tag semantic F1: {agg.get('tag_semantic_f1_pct')}%"
        )
        print(
            f"  [INFO] Skill precision: {agg.get('skill_precision_pct')}%  |  "
            f"skill recall@4: {agg.get('skill_recall_at_n_pct')}%"
        )
        print(
            f"  [INFO] Retrieval quality: {agg.get('retrieval_quality')}"
        )
        print(
            "  [INFO] Generation speed: "
            f"{agg.get('avg_tokens_per_sec')} tok/s"
        )
        print(
            f"  [INFO] Token usage: {agg.get('total_tokens')} tokens  |  "
            f"cost: ${agg.get('est_total_cost_usd')}  |  "
            f"cost/1000 files: ${agg.get('est_cost_per_1000_files_usd')}  |  "
            f"throughput: {agg.get('est_items_per_hour')} files/hr"
        )

    # ── PER-FILE RESULTS ──────────────────────────────────────────────────────

    print(f"\n{'=' * 90}")
    print("PER-FILE RESULTS")
    print(f"{'=' * 90}")

    per_file_cols = [
        "file_name",
        "model_name",
        "difficulty_level",
        "diff_correct",
        "tag_jaccard",
        "tag_precision",
        "tag_recall",
        "skill_jaccard",
        "skill_precision",
        "skill_recall",
        "confidence",
        "is_valid_output",
        "latency_sec",
        "latency_sec_client",
    ]

    print(
        df_scored[
            [c for c in per_file_cols if c in df_scored.columns]
        ].to_string(index=False)
    )

    # ── SAVE ──────────────────────────────────────────────────────────────────

    df_scored.to_csv(
        os.path.join(args.out, "scored_results.csv"),
        index=False,
    )

    summary_df.to_csv(
        os.path.join(args.out, "benchmark_summary.csv"),
        index=False,
    )

    summary_df.to_excel(
        os.path.join(args.out, "benchmark_summary.xlsx"),
        index=False,
        engine="openpyxl",
    )

    print(f"\nAll results saved to {args.out}/")

else:
    print(
        f"\nGold set not found at {args.gold} — skipping accuracy scoring."
    )
    print(f"Results saved to {args.out}/all_results.csv")
