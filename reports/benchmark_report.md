# Final Benchmark Report

## CTCM - Content Tagging & Competency Mapping

**Team 2 | Capstone Track 7 | AIDC 2026**

**Models:** Qwen2.5-VL-3B-Instruct-AWQ | GPT-4o-mini  
**Final revision:** 29 September 2026

| Benchmark scope | Result |
| --- | --- |
| Golden Set files | 12 |
| Successful concurrent requests per model | 9/9 |
| Active Qwen inference requests | 3 |

## Executive Summary

CTCM compares a locally served Qwen model with GPT-4o-mini through the OpenAI API, using the same human-reviewed Golden Set and three-pass pipeline. GPT-4o-mini showed stronger results in tagging and difficulty classification; Qwen showed advantages in skill mapping and final sequential end-to-end latency. Both achieve 100% validity under the benchmark checks and complete every final concurrent request successfully.

The final concurrent test achieved 89 files/hour for Qwen and 100 files/hour for GPT-4o-mini. The appropriate model depends on workload and operational priorities. The report distinguishes benchmark results, dashboard observations, and provisional service objectives.

Benchmark period: 28 September 2026 (UTC+3). Dashboard captures also include 27 September. Findings are specific to this capstone workload.

---

## 1. Project Overview and Business Problem

This project evaluates AI-based approaches for the automated analysis of learning content, with a focus on content tagging, difficulty classification, and skills mapping.

The business challenge is to identify a solution that can reliably interpret educational materials, extract the most relevant topics and concepts, determine the appropriate level of difficulty, and map the content to an established skills taxonomy.

To support an evidence-based model selection, the project applies a consistent benchmarking framework that evaluates both task quality and operational performance. Key considerations include tagging accuracy, skills-mapping quality, structured-output reliability, latency, resource requirements, scalability, and inference cost.

The overall objective is to recommend a solution that combines reliable content understanding with efficient, scalable, and practical deployment characteristics.

## 2. Use Case and Scope

The use case focuses on applying AI to analyze learning content and generate structured outputs that support content tagging, difficulty classification, and skills mapping.

For each learning item, the system is expected to identify the most relevant topics and concepts, assign a difficulty level of Beginner, Intermediate, or Advanced, and map the content to relevant skills from the provided taxonomy. The system also returns supporting information, including a concise content summary, confidence score, and learning-objective notes.

The project scope includes the evaluation of GPT-4o-mini and Qwen/Qwen2.5-VL-3B-Instruct-AWQ using the same evaluation dataset, prompt structure, and output requirements. Model outputs are compared against a human-reviewed reference set to assess both task quality and operational performance.

The evaluation is based on the actual content of each file rather than file names, ensuring that model predictions reflect the learning material itself. The evaluated file formats are listed in Section 5.

### Intended Output Contract

The CTCM pipeline is designed to return a consistent structured result for every analyzed learning item. The prompt, normalization logic, and scoring pipeline together define the expected output.

| Field | Intended requirement | Pipeline handling |
| --- | --- | --- |
| Content summary | One sentence describing what a learner does or learns | Returned as normalized text |
| Topic tags | 8–12 specific topic tags | Cleaned and deduplicated; benchmark validity requires a non-empty tag list |
| Difficulty | Beginner, Intermediate, or Advanced | Normalized and validated against the allowed labels |
| Competency mappings | Exactly four skills from the 136-skill taxonomy | Grounded against the taxonomy and normalized to four skills |
| Confidence | Numeric value from 0 to 1 | Converted to numeric form and constrained to the 0–1 range |
| Notes | Exactly three action-oriented learning objectives | Normalized as text; benchmark validity requires a non-empty value |

> **Structured-output validity**
>
> The 100% Structured-Output Validity reported in Section 7.1 indicates that all benchmark outputs passed the structural checks implemented in `scorer.py`, including successful parsing, a recognized difficulty label, numeric confidence, and non-empty tags, skills, and notes. Some additional output requirements are handled earlier by the prompt and normalization pipeline rather than being scored as separate benchmark metrics. Therefore, structured-output validity should be interpreted as a reliability measure for the response structure, not as a measure of semantic prediction accuracy.

## 3. Models Tested

The benchmark evaluated two models representing distinct deployment approaches: a commercial API-based model and an open-weight model deployed within the project infrastructure.

### GPT-4o-mini

GPT-4o-mini was used as the commercial reference model to establish a strong quality baseline for content tagging, difficulty classification, and skills mapping. It was evaluated using the same dataset, prompt structure, and structured-output requirements applied throughout the benchmark.

### Qwen/Qwen2.5-VL-3B-Instruct-AWQ

Qwen/Qwen2.5-VL-3B-Instruct-AWQ was selected as the open-weight deployment candidate. The AWQ 4-bit quantized variant (`model.safetensors`: 3.4 GB, source: `huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct-AWQ`) was deployed locally on an NVIDIA RTX A6000 GPU (46,068 MiB VRAM, confirmed via `nvidia-smi`) via vLLM AsyncLLMEngine.

Both models were evaluated under a consistent 3-pass inference methodology:

- **Pass 1:** tags and initial skills from the full 136-skill list.
- **Pass 2:** RAG-based skill re-pick from the top-15 candidate pool, conditional on Pass 1 producing tags.
- **Pass 3:** difficulty refinement.

This methodology supports a consistent comparison across task quality and operational characteristics.

## 4. Deployment Architecture

The application is containerised using Docker (image: **noura93/content-tagging:gpu-v1**) and deployed on Kubernetes (k3s) in the **ctcm** namespace using a single-replica deployment.

The pod is configured with the following resources per `k8s/deployment.yaml`:

**Requests:** 2 CPU cores, 8 GiB memory, 1 NVIDIA GPU  
**Limits:** 4 CPU cores, 16 GiB memory, 1 NVIDIA GPU

The application is served through Uvicorn with 1 worker on port 8000. A NodePort service exposes the endpoint externally on port 30801.

Readiness probes use:

- Period: 10 s
- Failure threshold: 10
- Timeout: 120 s

Liveness probes use:

- Initial delay: 300 s
- Period: 300 s

Both monitor the `/health` endpoint.

A persistent volume claim (`hf-cache-pvc`, 20 GiB) provides model-weight caching through `HF_HOME`. Sensitive credentials are managed through Kubernetes Secrets (`ctcm-secrets`).

The vLLM AsyncLLMEngine is configured with:

- `max_model_len=8192`
- `gpu_memory_utilization=0.85`
- `quantization=awq`

The RAG module uses `BAAI/bge-m3` on CPU with `RAG_POOL_K=15` and RRF fusion and is shared across both model paths.

Prometheus is exposed through NodePort 30900 and scrapes `/metrics` every 15 seconds. Grafana is exposed through NodePort 30301 and provides live observability.

## 5. Evaluation Dataset and Annotation Process

The evaluation dataset comprises **12 learning-content items** spanning four formats:

- `.pptx`
- `.ipynb`
- `.xlsx`
- `.md`

The materials cover topics in Python, Machine Learning, SQL, and Data Science.

Each item is paired with a human-reviewed reference record from `Golden-set-Reviewed.xlsx`, defining the expected content type, reference tags, difficulty level, mapped skills, and supporting notes. These serve as the benchmark ground truth.

Difficulty classifications were standardised across three levels:

- Beginner
- Intermediate
- Advanced

Both models were assessed against the same reviewed reference set and evaluated based on actual file content, not file names.

## 6. Evaluation Methodology

Model performance was evaluated using `scorer.py` against the reviewed Golden Set.

| Evaluation area | Measurement |
| --- | --- |
| Difficulty | Direct label comparison |
| Tagging | Tag precision, recall, strict Jaccard overlap, semantic F1 |
| Skills mapping | Jaccard overlap, precision, recall |
| RAG retrieval | Pool recall: gold skills in the top-15 pool |
| Validity | Benchmark parsing and required-field checks on normalized output |
| Operational | Client E2E latency, token usage, reported generation speed, exported cost estimates and throughput |

Results were computed per file across 12 items and aggregated per model.

### Data Sources Used in This Report

| Evidence | Authoritative source |
| --- | --- |
| Final quality and sequential results | `results_final/benchmark_summary.csv` and per-file CSVs for both models |
| Final concurrent load test | Final `README.md` and `observability/slo-targets.md`; methodology in `evaluation/concurrent_benchmark.py` |
| Concurrent test console captures | Screenshots of the script output and live three-request check in `docs/images/` |
| Service targets and observations | `observability/slo-targets.md` and the exported Grafana dashboard |
| Deployment and metric definitions | Kubernetes manifests and application code |

---

## 7. Benchmark Results

### 7.1 Model Quality Metrics

Source: `results_final/benchmark_summary.csv` — both models, 12 files each.

| Metric | Qwen | GPT-4o-mini |
| --- | ---: | ---: |
| Evaluation Items | 12 | 12 |
| Tagging / Classification Accuracy | 41.8% | **50.1%** |
| Difficulty Accuracy | 66.7% | **83.3%** |
| Tag Semantic F1 | 43.4% | **53.4%** |
| Tag Precision | **31.9%** | 29.1% |
| Tag Recall | 23.7% | **24.4%** |
| Tag Overlap (Strict Jaccard) | **17.0%** | 16.9% |
| Skills-Mapping Accuracy (Jaccard) | **27.0%** | 24.5% |
| Skill Precision | **35.4%** | 33.3% |
| Skill Recall (at N) | **47.2%** | 44.4% |
| RAG Pool Recall | 86.1% | 86.1% |
| Structured-Output Validity | 100% | 100% |

### How to Interpret the Quality Metrics

**Tagging / Classification Accuracy** is the project-specific composite of difficulty accuracy and strict tag Jaccard, averaged equally. It is not a standalone exact-match tag accuracy measure.

**Skills-Mapping Accuracy** is the mean Jaccard overlap with the reference skills.

**Structured-Output Validity** is retained exactly as reported. The scorer checks parsing, recognized difficulty, a numeric confidence value, and non-empty tags, skills, and notes after normalization. A 100% score means the outputs passed those checks. It does not mean every prediction is semantically correct or that every output-contract constraint in Section 2 was independently scored.

> **Quality result**
>
> GPT-4o-mini showed stronger results on the main tagging and difficulty measures. Qwen showed stronger results on skills mapping. Retrieval recall and benchmark validity were equal for both model paths.

### 7.2 Infrastructure & Inference Benchmark

Both columns below use `results_final/benchmark_summary.csv` as the final 12-file benchmark reference.

| Metric | Qwen | GPT-4o-mini |
| --- | ---: | ---: |
| Avg E2E Latency (client-measured) | **56.39 s** | 71.98 s |
| Avg Generation Speed (reported) | 29.16 tok/s | **105.67 tok/s** |
| Total Token Usage (12 files) | 107,195 | 287,621 |
| Avg Tokens per File | 8,933 | 23,968 |
| Est. Throughput (sequential) | 63.8 files/hr | 50.0 files/hr |
| Exported Est. Total Cost (12 files) | $0.057493 | $0.074621 |
| Exported Est. Cost per 1,000 Files | $4.79 | $6.22 |
| TTFT / TPOT in final CSV outputs | Not recorded | Not recorded |

E2E means the complete client-observed request. The per-file exports confirm that the final average latency values come from `latency_sec_client`.

The reported tok/s metric uses completion tokens divided by the separately recorded inference latency; it is not an isolated decode-speed measurement.

Cost estimates require the qualification described in Section 9.

| Infrastructure dimension | Qwen | GPT-4o-mini |
| --- | --- | --- |
| Model size / quantization | 3B parameters; AWQ 4-bit; reported 3.4 GB weight file | Model size not disclosed in project evidence; external API |
| GPU / context | RTX A6000; 46,068 MiB reported VRAM; 8,192-token configured limit | Provider GPU and serving limits not recorded in this benchmark |
| Application pod resources | Shared CTCM pod: CPU 2 / 4 cores; memory 8 / 16 GiB request / limit; 1 GPU allocated for Qwen | Uses the same CTCM application pod; no team-managed inference GPU for this backend |
| Serving / concurrency | vLLM AsyncLLMEngine; continuous batching; Uvicorn 1 worker | External OpenAI API; provider batching is not observable or controlled by the team |
| Observability | Application metrics plus native vLLM runtime metrics | Application request, latency, throughput and error metrics; provider internals unavailable |
| RAG integration | BAAI/bge-m3; CPU; top-15; RRF | Same shared module |

### 7.3 Concurrent Load Test

The concurrent benchmark is a **separate workload** from the 12-file benchmark and is not stored in `results_final/`. It was run with `evaluation/concurrent_benchmark.py`.

The final test used **3 simultaneous user sessions**, each submitting the same 3 files sequentially:

- Pandas Basics
- Decision Trees
- ML Workflow

This produced **9 requests per model**, with up to 3 client requests in flight. A separate one-user run of the same three files provided each model's baseline.

| Metric | Qwen | GPT-4o-mini |
| --- | ---: | ---: |
| Total Requests | 9 | 9 |
| Successful Requests | **9/9** | **9/9** |
| Sequential Baseline (3 files) | 149.2 s | 125.6 s |
| Sequential Average per File | 49.7 s | 41.9 s |
| Concurrent Wall Time (9 requests) | 362.3 s | 324.4 s |
| Concurrent Average Latency per File | 120.8 s | 108.1 s |
| Serial Estimate (9 requests) | 447.5 s | 376.8 s |
| Workload Speedup | **1.24x** | **1.16x** |
| Concurrent Throughput | **89 files/hr** | **100 files/hr** |

The concurrent benchmark is a separate workload from the 12-file final benchmark. Its results are based on a three-file workload executed under one-user baseline and three-user concurrent conditions.

![Concurrent benchmark summary printed by evaluation/concurrent_benchmark.py for Qwen and OpenAI](../docs/images/concurrent-benchmark-summary.png)

*Figure 1. Console summary printed by `evaluation/concurrent_benchmark.py`. Success 9/9 for both models; workload speedup 1.24x for Qwen and 1.16x for GPT-4o-mini; throughput 89 and 100 files/hour.*

> **Calculation method**
>
> **Workload speedup** = (one-user sequential total × 3 users) / concurrent wall time.  
> **Throughput** = successful requests / concurrent wall time × 3,600.  
> **Average request latency** = mean of individually timed successful requests, not wall time divided by 9.

The three sessions submit identical files at the same time, so the workload measures contention on a small, repeated input set rather than diverse concurrent traffic. Per-file timings for both runs are listed in Appendix C.

### Continuous Batching Evidence

Runtime evidence reported:

```text
Running: 3 reqs
Pending: 0 reqs
```

Prometheus also recorded:

```text
vllm:num_requests_running = 3
```

This shows three active Qwen inference requests inside the vLLM engine. Individual CTCM pipelines still contain sequential processing stages.

A separate live check launched three Qwen requests simultaneously against the deployed upload endpoint:

```text
POST /v1/tag/upload
model=qwen
NodePort 30801
```

All three returned HTTP 200 successfully.

![Three simultaneous curl requests to the Qwen upload endpoint, all returning HTTP 200](../docs/images/concurrent-requests-validation.png)

*Figure 2. Live validation of three simultaneous Qwen requests using `Decision Trees Revised.pptx`, all returning HTTP 200.*

Both model paths improved total workload completion time relative to their own serial estimates, while mean per-request latency increased under load.

OpenAI provider-side batching behavior is not observable or controlled by the team.

---

## 8. Accuracy / Task Performance Analysis

The quality results from `results_final/` indicate that GPT-4o-mini performed better on the core content-understanding tasks.

GPT-4o-mini achieved **50.1% tagging/classification accuracy** compared with **41.8% for Qwen**, while difficulty-classification accuracy reached **83.3% compared with 66.7%**. Tag semantic F1 was **53.4% vs 43.4%**.

Qwen showed stronger performance on skills mapping:

- Skills-mapping accuracy: **27.0% vs 24.5%**
- Skill precision: **35.4% vs 33.3%**
- Skill recall: **47.2% vs 44.4%**

Both models achieved identical **RAG pool recall of 86.1%** and **100% structured-output validity** across all 12 files.

## 9. Latency and Token / Cost Analysis

Qwen achieved a lower average client-measured end-to-end latency of **56.39 seconds** per item compared with **71.98 seconds** for GPT-4o-mini, resulting in higher estimated sequential throughput of **63.8 vs 50.0 files/hour**.

These are the final 12-file benchmark results.

GPT-4o-mini achieved higher reported generation speed:

- GPT-4o-mini: **105.67 tok/s**
- Qwen: **29.16 tok/s**

This metric uses the recorded inference timer and does not measure the complete request path. E2E latency also includes extraction, retrieval, other application work, and request overhead. A higher reported tok/s value therefore does not imply lower user-perceived latency.

Qwen used fewer total tokens:

- Qwen: **107,195**
- GPT-4o-mini: **287,621**

Average tokens per file were:

- Qwen: **8,933**
- GPT-4o-mini: **23,968**

These counts are specific to each model's tokenizer, prompts, and multi-pass processing and are not a controlled measure of equal semantic work.

The final export reports estimated totals of:

- Qwen: **$0.057493**
- GPT-4o-mini: **$0.074621**

Equivalent exported estimates per 1,000 files are:

- Qwen: **$4.79**
- GPT-4o-mini: **$6.22**

These values are benchmark estimates rather than verified production prices or provider billing.

> **Cost-accounting qualification**
>
> The supplied upload endpoint passes an empty backend value to `score_file()`, whose non-OpenAI branch uses GPU-time-based costing. The OpenAI model module separately defines token-based costing, but that branch is not selected by this endpoint. The exported OpenAI estimate therefore needs reconciliation before a production cost recommendation.
>
> The configured assumptions are $0.35/GPU-hour, $0.000150/1K OpenAI input tokens, and $0.000600/1K output tokens. These are project assumptions, not a current price quotation.

In the final concurrent test, throughput reached **89 files/hour for Qwen** and **100 files/hour for GPT-4o-mini**, with workload speedups of **1.24x** and **1.16x** respectively.

Each speedup is measured against that model's own three-file sequential baseline.

---

## 10. Deployment and Operational Trade-offs

GPT-4o-mini provides a simpler inference operating model with no team-managed inference GPU, stronger tagging and difficulty accuracy, and application-level monitoring through CTCM.

It introduces dependencies on an external API, quota, and billing, while provider-side inference internals remain unavailable to the team.

The Qwen deployment requires GPU capacity, Docker, Kubernetes, and model-serving ownership. It provides direct infrastructure control, native vLLM metrics, stronger skills mapping, and demonstrated concurrent processing.

Its lower exported cost estimate remains subject to the accounting qualification in Section 9.

| Criterion | Qwen | GPT-4o-mini |
| --- | ---: | ---: |
| Tagging accuracy | 41.8% | 50.1% |
| Difficulty accuracy | 66.7% | 83.3% |
| Skills mapping | 27.0% | 24.5% |
| Avg E2E latency | 56.39 s | 71.98 s |
| Sequential / concurrent throughput | 63.8 / 89 files/hr | 50.0 / 100 files/hr |
| Concurrent workload speedup | 1.24x | 1.16x |
| Exported est. cost / 1,000 files | $4.79 | $6.22 |
| Structured validity | 100% | 100% |
| Inference visibility | Team-managed vLLM metrics | Provider internals unavailable |
| Inference infrastructure control | Team-managed | Provider-managed |

The appropriate model depends on workload and operational priorities, including quality requirements, latency and throughput targets, validated cost, observability needs, and the team's capacity to operate GPU infrastructure.

### Data-Handling Boundary

Qwen inference runs in team-managed infrastructure through the k3s cluster and GPU node described in Section 4.

GPT-4o-mini requests are sent to an external API operated by OpenAI.

This describes where inference executes rather than providing a privacy or compliance assessment. The benchmark did not test network egress, data residency, retention terms, or regulatory requirements. Any use involving sensitive content would require a separate review of applicable policies and provider terms.

---

## 11. Live Service Demonstration

The deployed service was demonstrated through the live CTCM endpoint.

The demonstration included:

- Uploading `.ipynb` files through `POST /v1/tag/upload`
- Running requests with `model=qwen`
- Running requests with `model=openai`
- Comparing structured `TagResult` responses
- Running the concurrent benchmark with 3 users and 3 files
- Observing Qwen batching behavior through Grafana
- Checking `/health`
- Checking `/v1/models`
- Checking `/metrics`

The Streamlit interface provides file upload, model selection, and structured-result review.

The demonstrated endpoints represent the recorded capstone lab environment and do not establish continuing public availability.

**AI Hub scope:** AI Hub deployment was optional for the final presentation and was deferred until after the presentation based on instructor guidance communicated to the team. The completed capstone demonstration therefore focuses on the implemented CTCM service, model comparison, Kubernetes deployment, benchmarking, concurrency, and observability.

---

## 12. Live Observability

The following observations come from the CTCM Prometheus/Grafana record for 27–28 September 2026 and the final SLO record for 28 September (UTC+3).

They describe captured benchmark and monitoring windows rather than a single continuous production measurement.

Application metrics cover both model paths. Native vLLM metrics cover Qwen only.

### 12.1 Service Availability

Availability was high during normal operation but temporarily decreased during pod restart and deployment activity.

The final SLO record reports **94.2%** during one recent one-hour window, below the proposed **99%** target.

Prometheus `up` measures scrape reachability and does not by itself prove that every user request succeeds.

### 12.2 Qwen Requests and Request Rate

The dashboard record reports **29 successful Qwen requests** in a 12-hour observation window on 28 September.

Request counts reflect the selected labels and dashboard window and should not be interpreted as the 12-file benchmark sample size.

Successful Qwen request rate peaked at approximately **1.80 requests/minute** in the captured one-minute query window, with OpenAI activity visible in the same dashboard panel.

### 12.3 Concurrent Requests on the GPU

The running-request metric reached **3 simultaneous Qwen inference requests**.

Together with successful client requests and vLLM runtime evidence, this demonstrates active concurrent inference through AsyncLLMEngine during the tested workload.

It does not establish the maximum sustainable concurrency of the service.

### 12.4 Full-Pipeline E2E Latency

The dashboard record showed Qwen p50 reaching approximately **2.50 minutes** during peak concurrent load.

The final SLO record describes p95 approaching approximately **3 minutes**.

The final sequential means were:

- Qwen: **56.39 s**
- GPT-4o-mini: **71.98 s**

The final concurrent average request latencies were:

- Qwen: **120.8 s**
- GPT-4o-mini: **108.1 s**

Means, percentiles, model-specific series, and measurement windows represent different measurements and should be interpreted separately.

Higher E2E latency under concurrent load is consistent with waiting and shared-resource contention, although these observations do not isolate a single cause.

### 12.5 TTFT and TPOT

Qwen's vLLM panels expose:

- Time to First Token (TTFT)
- Time per Output Token (TPOT)

The captured TPOT p95 was approximately **61.9 ms/token**, with p50 around **38–40 ms/token** during lighter load.

These are inference-engine diagnostics rather than full-pipeline latency measurements.

No comparable provider-side GPT-4o-mini TTFT or TPOT measurements were captured, and the final benchmark CSV does not contain these metrics.

### 12.6 Qwen Request Queue Time

The dashboard record showed p95 queue time reaching approximately **60 seconds** during concurrent traffic and remaining near zero during lighter load.

This demonstrates waiting inside the serving engine during the captured period. It does not mean that the complete application workload executed serially.

### 12.7 Prompt and Generation Throughput

Prompt-processing throughput reached approximately **534 prompt tokens/second** during concurrent Qwen activity.

The dashboard also displayed generation throughput.

Prompt-processing throughput and output generation speed represent different work and should not be compared as if they were the same metric.

The running-request metric is the direct evidence of simultaneously active inference requests.

### 12.8 Process Virtual Memory

The recorded process virtual-memory range was approximately **65–75 GiB**, including a captured value around **66.5 GiB**.

The query divides bytes by `1024³`, so GiB is the appropriate unit.

Virtual address space includes mapped files, shared libraries, and reservations and should not be interpreted as physical RAM consumption.

### 12.9 Request Error Rate

The final SLO record reports **0% application error rate** in its latest dashboard observation.

Separately, the final concurrent benchmark completed:

- Qwen: **9/9 successful**
- GPT-4o-mini: **9/9 successful**

These results demonstrate zero observed failures in that concurrent test, rather than long-term reliability.

Error-rate interpretation requires available telemetry and nonzero request traffic during the same measurement window.

> **Measurement boundaries**
>
> **Application layer:** reachability, request outcomes, E2E latency, and successful throughput.  
> **Qwen engine layer:** active and waiting requests, TTFT, TPOT, queue time, KV-cache, and token throughput.  
> **Offline evaluation:** tags, difficulty, skills, retrieval recall, and output validity.

### Latency Measurement Reference

| Measure | Scope | Available for |
| --- | --- | --- |
| Client E2E latency | Full client-observed request including extraction, retrieval, inference, and response | Qwen and GPT-4o-mini |
| Application histogram latency | Full pipeline as recorded by the service request histogram | Qwen and GPT-4o-mini |
| Model / inference latency | Separately recorded inference timer; basis of reported tok/s | Qwen and GPT-4o-mini as recorded by the application |
| Generation speed (tok/s) | Completion tokens / inference latency | Qwen and GPT-4o-mini |
| TTFT, TPOT, queue time | vLLM engine internals | Qwen only |

The custom request histogram uses buckets at:

```text
1
2.5
5
10
20
30
60
120
180
300
600 seconds
```

The 180-second boundary supports measurement around the proposed latency objective, while short monitoring windows and limited request counts should still be considered when interpreting percentiles.

---

## 13. Lessons Learned

A standardised evaluation process using the same dataset, prompt structure, three-pass inference pipeline, output schema, and scoring framework was essential for a consistent comparison.

### Asynchronous Serving Enables Concurrency

The async upload endpoint and awaited Qwen call enabled concurrent requests to reach vLLM.

In the final concurrent run, Qwen:

- Completed **9/9 requests**
- Achieved **1.24x workload speedup**
- Reached **3 active inference requests**

This demonstrated that the asynchronous serving path allowed multiple Qwen inference requests to be active in vLLM at the same time.

### Instrument the Quantity Being Claimed

The client E2E timer, application histogram, and internal inference timer answer different performance questions.

Histogram buckets that include long-running requests are necessary for meaningful latency panels.

Generation speed, prompt throughput, queue time, and E2E latency must retain their own units and measurement scopes.

### Retrieval Is Not Final Skill Selection

Both models achieved **86.1% RAG pool recall**, while final skill-mapping accuracy was lower and differed between models.

Retrieval can supply relevant candidates without guaranteeing correct final skill selection.

### Service Objectives Need Explicit Evidence

The final run supports successful short-workload concurrency and throughput.

Availability did not meet its proposed target in the reported one-hour window.

The p95 latency observation approached the proposed 180-second boundary, so a larger measurement window would be needed for stronger service-level validation.

Exported cost estimates should also be validated against the final accounting path and actual provider billing before production use.

### Final Assessment

CTCM combines:

- Multi-format content extraction
- RAG
- Local and API-based inference
- Docker
- Kubernetes / k3s
- FastAPI
- vLLM
- Prometheus
- Grafana
- Streamlit

GPT-4o-mini showed stronger results in tagging and difficulty classification.

Qwen showed advantages in skills mapping and final sequential E2E latency while also providing direct control over the local inference infrastructure and vLLM observability.

Both model paths passed the benchmark validity checks and completed the final concurrent workload successfully.

Model selection should weigh quality, E2E latency, throughput, validated cost, observability, and operating responsibility.

The 12-file Golden Set benchmark and 9-request-per-model concurrent workload demonstrate the capstone use case; they do not establish maximum production capacity or long-term service-level compliance.

---

## 14. Optional Future Work

The following items are **future proposals only**. None was implemented or benchmarked as part of the final project results.

1. **Intelligent model routing**  
   Explore routing requests between local Qwen and an external API model based on factors such as file type, file size, complexity, or current infrastructure load. Any routing strategy would require separate evaluation of quality, latency, cost, and data-handling implications.

2. **Multi-GPU / multi-worker scaling**  
   Investigate whether additional workers, replicas, or GPUs improve throughput and tail latency beyond the single-replica, single-GPU, one-Uvicorn-worker configuration tested in the capstone.

3. **Queue-depth signals for autoscaling**  
   Evaluate vLLM waiting-request or queue-depth metrics as possible inputs for future autoscaling decisions.

4. **Human-in-the-loop curriculum review**  
   Consider a review workflow in the Streamlit interface where curriculum reviewers can approve or adjust predicted tags and competency mappings before final acceptance.

---

# Appendix A - Service Indicators & Proposed SLOs

Source of targets: `observability/slo-targets.md`.

Service: CTCM `/v1/tag/upload` in namespace `ctcm`  
Measurement date: **28 September 2026 (UTC+3)**

These are provisional capstone objectives rather than production commitments.

| Indicator & target | Window / observed evidence | Assessment |
| --- | --- | --- |
| **Availability ≥99%** — Service scrape reachability | 1-hour query during scheduled service. **94.2%** in the reported restart/deployment-affected window | **Not met** in that window |
| **p95 E2E latency ≤180 s** per model | 5-minute histogram/rate window during active traffic. p95 approached approximately 3 minutes | **Insufficient evidence** for exact per-model compliance |
| **Successful throughput ≥50 files/hour/model** | Complete concurrent workload: Qwen **89/hr**, GPT-4o-mini **100/hr** | **Met** for the measured concurrent runs |
| **Request error rate ≤1%** | Latest record: 0%; final concurrency: **0/9 failures per model** | **Met** for the observed test; limited sample |
| **Qwen concurrency ≥3** without request failure | **3 active vLLM requests** and **9/9 successful Qwen requests** | **Demonstrated** for the tested workload |

### How the Targets Are Applied

- **Availability** covers scheduled service windows rather than 24/7 operation. Prometheus scrape reachability is a CTCM service indicator rather than a measurement of OpenAI provider availability.
- **Latency** is evaluated separately for each model. A sequential average cannot substitute for p95 latency under concurrent traffic.
- **Throughput** is workload-specific. The three-file concurrent workload differs from the 12-file Golden Set benchmark.
- **Error rate** requires real request traffic and available telemetry during the same measurement period.
- **Concurrency** demonstrates support for three active Qwen requests but does not establish maximum capacity.
- Quality scores such as skill mapping and RAG pool recall remain offline benchmark results and are reported separately from service-level objectives.

---

# Appendix B - Prometheus Query Reference

The following expressions correspond to the metrics used in the final observability analysis.

## Service Availability — Percent, 1 Hour

```promql
100 * avg_over_time(up{job="content-tagging"}[1h])
```

## Successful Qwen Requests — 12-Hour Observation

```promql
sum(increase(model_requests_total{
  model="qwen",
  status="success"
}[12h]))
```

## Active Qwen Inference Requests

```promql
vllm:num_requests_running{model_name=~".*Qwen.*"}
```

## Successful Requests per Minute by Model

```promql
60 * sum by (model) (
  rate(model_requests_total{
    model=~"qwen|openai",
    status="success"
  }[5m])
)
```

## Full-Pipeline p95 E2E Latency — Seconds per Model

```promql
histogram_quantile(
  0.95,
  sum by (le, model) (
    rate(model_request_duration_seconds_bucket{
      model=~"qwen|openai"
    }[5m])
  )
)
```

## Qwen p95 TPOT — Milliseconds per Token

```promql
1000 * histogram_quantile(
  0.95,
  sum by (le) (
    rate(vllm:time_per_output_token_seconds_bucket{
      model_name=~".*Qwen.*"
    }[5m])
  )
)
```

## Qwen p95 Queue Time — Seconds

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(vllm:request_queue_time_seconds_bucket{
      model_name=~".*Qwen.*"
    }[5m])
  )
)
```

## Qwen Prompt-Processing Throughput — Tokens per Second

```promql
sum(
  rate(vllm:prompt_tokens_total{
    model_name=~".*Qwen.*"
  }[1m])
)
```

## Process Virtual Address Space — GiB

```promql
process_virtual_memory_bytes{job="content-tagging"}
  / 1024 / 1024 / 1024
```

For p50, replace `0.95` with `0.50`.

The captured request-rate peak used a one-minute query, while the SLO record specifies a five-minute rate window. Query scopes should remain restricted to the intended CTCM deployment.

---

# Appendix C - Evidence & Reproducibility

## Error Rate: Evaluate Only with Valid Traffic

```promql
100 * (
  sum(rate(model_requests_total{status="error"}[5m]))
  or vector(0)
) /
clamp_min(
  sum(rate(model_requests_total[5m]))
  or vector(0),
  0.000000001
)
```

The dashboard query can display zero when telemetry is missing or traffic is absent. Error-rate interpretation therefore requires a healthy scrape target and positive request traffic in the same window.

## Concurrent Test Evidence Captures

The captures below show the per-model console outputs corresponding to the final concurrent workload.

![Qwen concurrent benchmark console output: 3 users x 3 files](../docs/images/concurrent-qwen.png)

*Figure C1. Qwen: baseline 149.2 s; average baseline 49.7 s/file; concurrent wall time 362.3 s; concurrent average latency 120.8 s/file; workload speedup 1.24x; throughput 89 files/hour; 9/9 successful.*

![OpenAI concurrent benchmark console output: 3 users x 3 files](../docs/images/concurrent-openai.png)

*Figure C2. GPT-4o-mini: baseline 125.6 s; average baseline 41.9 s/file; concurrent wall time 324.4 s; concurrent average latency 108.1 s/file; workload speedup 1.16x; throughput 100 files/hour; 9/9 successful.*

### Per-File Latencies from the Captures

| File | Qwen baseline | Qwen concurrent (users 1–3) | GPT-4o-mini baseline | GPT-4o-mini concurrent (users 1–3) |
| --- | ---: | --- | ---: | --- |
| Pandas Basics | 38.8 s | 92.4 / 92.4 / 92.4 s | 31.4 s | 76.7 / 77.5 / 77.2 s |
| Decision Trees | 58.7 s | 138.0 / 138.0 / 138.0 s | 49.6 s | 132.9 / 133.1 / 134.3 s |
| ML Workflow | 51.6 s | 131.9 / 131.9 / 131.9 s | 44.6 s | 114.8 / 113.8 / 112.9 s |

Displayed per-file values are rounded, so their sums may differ slightly from the reported aggregate totals.

## Reproduction

Run the final 12-file benchmark against the same Golden Set:

```bash
python evaluation/run_benchmark.py \
  --server http://<HOST>:8000 \
  --data-dir ./data \
  --gold ./data/Golden-set-Reviewed.xlsx \
  --models openai,qwen \
  --out ./results_final
```

Run the three-user concurrent workload:

```bash
python evaluation/concurrent_benchmark.py
```

The canonical 12-file benchmark outputs are stored in:

```text
results_final/
```

Concurrent benchmark evidence is retained in the repository documentation and `docs/images/`.
