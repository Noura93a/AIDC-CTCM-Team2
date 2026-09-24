"""
schemas.py — request/response contracts for the content-tagging API.
Do not weaken these shapes; they are the contract's teeth.
"""
from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ── inbound ──────────────────────────────────────────────────────────────────

class TagRequest(BaseModel):
    """One file URL or base64 blob to tag."""
    file_url: Optional[str] = Field(None, description="Publicly reachable URL of the content file.")
    file_b64: Optional[str] = Field(None, description="Base64-encoded file bytes (fallback when no URL).")
    filename: str            = Field(..., description="Original filename including extension.")
    model: str               = Field("qwen", description="'openai' or 'qwen'")


class BenchmarkRequest(BaseModel):
    """Run both models on every file and return a side-by-side comparison."""
    file_urls: List[str]     = Field(..., description="List of publicly reachable file URLs.")
    filenames: List[str]     = Field(..., description="Matching list of original filenames.")


# ── per-file result ───────────────────────────────────────────────────────────

class TagResult(BaseModel):
    file_name:        str
    model_name:       str
    content_type:     str
    predicted_tags:   str   = Field("", description="Pipe-separated tag list.")
    difficulty_level: str   = ""
    predicted_skills: str   = Field("", description="Pipe-separated skill list.")
    confidence:       Optional[float] = None
    notes:            str   = ""
    content_summary:  str   = ""
    # quality vs gold
    tag_overlap_strict:    Optional[float] = None
    tag_semantic_f1:       Optional[float] = None
    tag_precision:         Optional[float] = None
    tag_recall:            Optional[float] = None
    difficulty_correct:    Optional[bool]  = None
    skill_mapping_jaccard: Optional[float] = None
    skill_recall_at_4:     Optional[float] = None
    skill_precision:       Optional[float] = None
    pool_recall:           Optional[float] = None
    is_valid_output:       bool = False
    n_hallucinated_skills: int  = 0
    # infra
    prompt_tokens:     int          = 0
    completion_tokens: int          = 0
    total_tokens:      int          = 0
    tokens_per_sec:    Optional[float] = None
    latency_sec:       float        = 0.0
    est_cost_usd:      float        = 0.0


# ── aggregate / benchmark report ─────────────────────────────────────────────

class ModelAggregate(BaseModel):
    model_name:                              str
    n_items:                                 int
    # 7 required metrics
    tagging_classification_accuracy_pct:     Optional[float] = None
    skill_mapping_accuracy_pct:              Optional[float] = None
    retrieval_quality:                       str             = ""
    structured_output_validity_pct:          float           = 0.0
    avg_latency_sec:                         float           = 0.0
    total_tokens:                            int             = 0
    est_total_cost_usd:                      float           = 0.0
    est_items_per_hour:                      float           = 0.0
    # extra metrics
    tag_semantic_f1_pct:                     Optional[float] = None
    tag_precision_pct:                       Optional[float] = None
    tag_recall_pct:                          Optional[float] = None
    skill_precision_pct:                     Optional[float] = None
    avg_tokens_per_sec:                      Optional[float] = None
    est_cost_per_1000_files_usd:             Optional[float] = None
    # diagnostics
    difficulty_accuracy_pct:                 Optional[float] = None
    tag_overlap_strict_pct:                  Optional[float] = None
    tagging_classification_accuracy_semantic_pct: Optional[float] = None
    skill_recall_at_n_pct:                   Optional[float] = None
    n_hallucinated_skills:                   int             = 0
    wall_sec:                                float           = 0.0


class BenchmarkReport(BaseModel):
    results:    List[TagResult]
    aggregates: List[ModelAggregate]
    winner:     str = Field("", description="Model with highest tagging_classification_accuracy_pct.")


# ── health / models ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: Literal["ok"]
    models: List[str]


class ModelCard(BaseModel):
    id:       str
    object:   Literal["model"] = "model"
    owned_by: str = "content-tagging-service"


class ModelList(BaseModel):
    object: Literal["list"] = "list"
    data:   List[ModelCard]