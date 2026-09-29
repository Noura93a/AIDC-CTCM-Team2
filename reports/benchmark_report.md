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

Qwen/Qwen2.5-VL-3B-Instruct-AWQ was selected as the open-weight deployment candidate. The AWQ 4-bit quantized variant (model.safetensors: 3.4 GB, source: huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct-AWQ) was deployed locally on an NVIDIA RTX A6000 GPU (46,068 MiB VRAM, confirmed via nvidia-smi) via vLLM AsyncLLMEngine.

Both models were evaluated under a consistent 3-pass inference methodology - Pass 1 (tags + initial skills from full 136-skill list), Pass 2 (RAG-based skill re-pick from top-15 pool, conditional on Pass 1 producing tags), and Pass 3 (difficulty refinement) - to support a fair comparison across task quality and operational characteristics.

## 4. Deployment Architecture

The application is containerised using Docker (image: **noura93/content-tagging:gpu-v1**) and deployed on Kubernetes (k3s) in the **ctcm** namespace using a single-replica deployment. The pod is configured with the following resources per k8s/deployment.yaml:

**Requests:** 2 CPU cores, 8 GiB memory, 1 NVIDIA GPU  
**Limits:** 4 CPU cores, 16 GiB memory, 1 NVIDIA GPU

The application is served through Uvicorn with 1 worker on port 8000. A NodePort service exposes the endpoint externally on port 30801. Readiness probes (period: 10s, failureThreshold: 10, timeout: 120s) and liveness probes (initialDelay: 300s, period: 300s) monitor the /health endpoint. A persistent volume claim (hf-cache-pvc, 20Gi) provides model weight caching via HF_HOME. Sensitive credentials are managed through Kubernetes Secrets (ctcm-secrets).

The vLLM AsyncLLMEngine is configured with max_model_len=8192, gpu_memory_utilization=0.85, and quantization=awq (config.py). The RAG module (BAAI/bge-m3, device=cpu, RAG_POOL_K=15, RRF fusion) runs on CPU and is shared across both models. Prometheus (NodePort 30900) scrapes /metrics every 15 seconds and Grafana (NodePort 30301) provides live observability.

## 5. Evaluation Dataset and Annotation Process

The evaluation dataset comprises 12 learning-content items spanning four formats: .pptx, .ipynb, .xlsx, .md, covering topics in Python, Machine Learning, SQL, and Data Science.

Each item is paired with a human-reviewed reference record from Golden-set-Reviewed.xlsx defining the expected content type, reference tags, difficulty level, mapped skills, and supporting notes. These serve as the benchmark ground truth (the human-reviewed Golden Set).

Difficulty classifications were standardised across three levels: Beginner, Intermediate, and Advanced. Both models were assessed against the same reviewed reference set and evaluated based on actual file content, not file names.

## 6. Evaluation Methodology

Model performance was evaluated using scorer.py against the reviewed golden reference.

| Evaluation area | Measurement |
| --- | --- |
| Difficulty | Direct label comparison |
| Tagging | Tag precision, recall, strict Jaccard overlap, semantic F1 |
| Skills mapping | Jaccard overlap, precision, recall |
| RAG retrieval | Pool recall: gold skills in the top-15 pool |
| Validity | Benchmark parsing and required-field checks on normalized output |
| Operational | Client E2E latency, token usage, reported generation speed, exported cost estimates and throughput |

Results were computed per file across 12 items and aggregated per model.

### Data sources used in this report

| Evidence | Authoritative source |
| --- | --- |
| Final quality and sequential results | **results_final/benchmark_summary.csv** and per-file CSVs for both models. [S1] |
| Final concurrent load test | Final README and SLO record; methodology in evaluation/concurrent_benchmark.py. [S2] |
| Concurrent test console captures | Screenshots of the script output and of the live three-request check (docs/images/). [S7] |
| Service targets and observations | observability/slo-targets.md and the Grafana dashboard record. [S3, S5] |
| Deployment and metric definitions | Kubernetes manifests and application code. [S4] |

## 7. Benchmark Results

### 7.1 Model Quality Metrics

Source: results_final/benchmark_summary.csv - both models, 12 files each. [S1]

| Metric | Qwen | GPT-4o-mini |
| --- | --- | --- |
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

### How to interpret the quality metrics

**Tagging / Classification Accuracy** is the project-specific composite of difficulty accuracy and strict tag Jaccard, averaged equally. It is not a standalone exact-match tag accuracy measure. Skills-mapping accuracy is the mean Jaccard overlap with the reference skills. [S4]

**Structured-output validity** is retained exactly as reported. The scorer checks parsing, recognized difficulty, a numeric confidence value, and non-empty tags, skills and notes after normalization. A 100% score means the outputs passed those checks. It does not mean every prediction is semantically correct or that every output-contract constraint in Section 2 was independently tested. [S4]

> **Quality result**
>
> GPT-4o-mini showed stronger results on the main tagging and difficulty measures. Qwen showed stronger results on skills mapping. Retrieval recall and benchmark validity are equal for both model paths.

### 7.2 Infrastructure & Inference Benchmark

Both columns below use results_final/benchmark_summary.csv. The comparison does not mix final results with intermediate after-fix measurements. [S1]

| Metric | Qwen | GPT-4o-mini |
| --- | --- | --- |
| Avg E2E Latency (client-measured) | **56.39 s** | 71.98 s |
| Avg Generation Speed (reported) | 29.16 tok/s | **105.67 tok/s** |
| Total Token Usage (12 files) | 107,195 | 287,621 |
| Avg Tokens per File | 8,933 | 23,968 |
| Est. Throughput (sequential) | 63.8 files/hr | 50.0 files/hr |
| Exported Est. Total Cost (12 files) | $0.057493 | $0.074621 |
| Exported Est. Cost per 1,000 Files | $4.79 | $6.22 |
| TTFT / TPOT in final CSV outputs | Not recorded | Not recorded |

E2E means the complete client-observed request. The per-file exports confirm that the final average latency values come from latency_sec_client. The reported tok/s metric uses completion tokens divided by the separately recorded inference latency; it is not an isolated decode-speed measurement. Cost estimates require the qualification in Section 9. [S1, S4]

| Infrastructure dimension | Qwen | GPT-4o-mini |
| --- | --- | --- |
| Model size / quantization | 3B parameters; AWQ 4-bit; reported 3.4 GB weight file | Model size not disclosed in project evidence; external API |
| GPU / context | RTX A6000; 46,068 MiB reported VRAM; 8,192-token configured limit | Provider GPU and serving limits not recorded in this benchmark |
| Application pod resources | Shared CTCM pod: CPU 2 / 4 cores; memory 8 / 16 GiB (request / limit); 1 GPU allocated for Qwen | Uses the same CTCM application pod; no team-managed inference GPU for this backend |
| Serving / concurrency | vLLM AsyncLLMEngine; continuous batching; Uvicorn 1 worker | External OpenAI API; provider batching is not observable or controlled by the team |
| Observability | Application metrics plus native vLLM runtime metrics | Application request, latency, throughput and error metrics; provider internals unavailable |
| RAG integration | BAAI/bge-m3; CPU; top-15; RRF | Same shared module |

### 7.3 Concurrent Load Test

The concurrent benchmark is a **separate workload** from the 12-file benchmark and is not stored in results_final/. It was run with evaluation/concurrent_benchmark.py.

The final test used **3 simultaneous user sessions**, each submitting the same 3 files sequentially: Pandas Basics, Decision Trees and ML Workflow. This produced **9 requests per model**, with up to 3 client requests in flight. A separate one-user run of the same files provided each model's baseline. [S2]

| Metric | Qwen | GPT-4o-mini |
| --- | --- | --- |
| Total Requests | 9 | 9 |
| Successful Requests | **9/9** | **9/9** |
| Sequential Baseline (3 files) | 149.2 s | 125.6 s |
| Sequential Average per File | 49.7 s | 41.9 s |
| Concurrent Wall Time (9 requests) | 362.3 s | 324.4 s |
| Concurrent Average Latency per File | 120.8 s | 108.1 s |
| Serial Estimate (9 requests) | 447.5 s | 376.8 s |
| Workload Speedup | **1.24x** | **1.16x** |
| Concurrent Throughput | **89 files/hr** | **100 files/hr** |

Values are reproduced from the final run. The 447.5 s Qwen serial estimate uses the unrounded baseline; multiplying the displayed 149.2 s by 3 gives a slightly different rounded value. The 3-file baseline is a separate workload from the 12-file final benchmark.

![Concurrent benchmark summary printed by evaluation/concurrent_benchmark.py for Qwen and OpenAI](../docs/images/concurrent-benchmark-summary.png)

*Figure 1. Console summary printed by evaluation/concurrent_benchmark.py. Success 9/9 for both models; speedup 1.24x (Qwen) and 1.16x (OpenAI); throughput 89 and 100 files/hr. The values match the table above. [S2, S7]*

> **Calculation method**
>
> **Workload speedup** = (one-user sequential total × 3 users) / concurrent wall time.  
> **Throughput** = successful requests / concurrent wall time × 3,600.  
> **Average request latency** = mean of individually timed successful requests, not wall time divided by 9.

The three sessions submit identical files at the same time, so the workload measures contention on a small, repeated input set rather than diverse concurrent traffic. Per-file timings for both runs are listed in Appendix C.

### Continuous Batching Evidence

Runtime evidence reported **Running: 3 reqs; Pending: 0 reqs**, and Prometheus recorded **vllm:num_requests_running = 3**. This shows three active Qwen inference requests inside the vLLM engine. Individual CTCM pipelines still contain sequential processing stages. [S2, S3]

A separate live check launched three Qwen requests at the same moment against the deployed upload endpoint (`POST /v1/tag/upload`, `model=qwen`, NodePort 30801). All three returned HTTP 200 with a total time of about 120.55 s each, starting at 18:52:14 and finishing at about 18:54:14.

![Three simultaneous curl requests to the Qwen upload endpoint, all returning HTTP 200](../docs/images/concurrent-requests-validation.png)

*Figure 2. Live validation of three simultaneous Qwen requests (Decision Trees Revised.pptx). This is a separate spot check, not part of the 9-request benchmark; its ~120.55 s per-request time should not be confused with the 120.8 s concurrent average in Section 7.3. [S2, S7]*

Both model paths improved total workload completion time relative to their own serial estimates, while mean per-request latency increased under load. OpenAI's provider-side batching behavior is not observable or controlled by the team.

## 8. Accuracy / Task Performance Analysis

The quality results from results_final/ indicate that GPT-4o-mini performed better on the core content-understanding tasks.

GPT-4o-mini achieved 50.1% tagging/classification accuracy compared with 41.8% for Qwen, while difficulty-classification accuracy reached 83.3% compared with 66.7%. Tag semantic F1 was 53.4% vs 43.4%.

Qwen showed stronger performance on skills mapping - 27.0% vs 24.5% - along with higher skill precision (35.4% vs 33.3%) and skill recall (47.2% vs 44.4%). Both models achieved identical RAG pool recall of 86.1% and 100% structured-output validity across all 12 files.

## 9. Latency and Token / Cost Analysis

Qwen achieved a lower average client-measured end-to-end latency of **56.39 seconds** per item compared with **71.98 seconds** for GPT-4o-mini, resulting in higher estimated sequential throughput of **63.8 vs 50.0 files/hour**. These are the final 12-file benchmark results. [S1]

GPT-4o-mini achieved higher reported generation speed (**105.67 vs 29.16 tok/s**). This metric uses the recorded inference timer and does not measure the complete request path. E2E latency also includes extraction, retrieval, other application work and request overhead. A higher reported tok/s value therefore does not imply lower user-perceived latency.

Qwen used fewer total tokens: **107,195 vs 287,621** across 12 files, averaging **8,933 vs 23,968** per file. Counts are specific to each model's tokenizer, prompts and multi-pass processing; they are not a controlled measure of equal semantic work.

The final export reports estimated totals of **$0.057493 for Qwen** and **$0.074621 for GPT-4o-mini**, equivalent to approximately **$4.79 vs $6.22 per 1,000 files**. These values are preserved as benchmark estimates, not verified production prices or provider billing.

> **Cost-accounting qualification**
>
> The supplied upload endpoint passes an empty backend value to score_file(), whose non-OpenAI branch uses GPU-time-based costing. The OpenAI model module separately defines token-based costing, but that branch is not selected by this endpoint. The exported OpenAI estimate therefore needs reconciliation before a production cost recommendation. The configured assumptions are $0.35/GPU-hour, $0.000150/1K OpenAI input tokens and $0.000600/1K output tokens. These are project assumptions, not a current price quotation. [S4]

In the final concurrent test, throughput reached **89 files/hour for Qwen** and **100 files/hour for GPT-4o-mini**, with workload speedups of **1.24x** and **1.16x**. Compare each speedup with its own 3-file baseline; do not attribute the entire change to batching alone.

## 10. Deployment and Operational Trade-offs

GPT-4o-mini provides a simpler inference operating model with no team-managed GPU, stronger tagging and difficulty accuracy, and application-level monitoring through CTCM. It introduces external API, quota and billing dependencies, while provider-side inference internals remain unavailable.

The Qwen deployment requires GPU capacity, Docker, Kubernetes and serving ownership. It provides direct infrastructure control, native vLLM metrics, stronger skills mapping and demonstrated concurrent processing. Its lower exported cost estimate remains subject to the accounting limitation in Section 9.

| Criterion | Qwen | GPT-4o-mini |
| --- | --- | --- |
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

The appropriate model depends on workload and operational priorities: quality requirements, latency and throughput targets, cost validation, observability needs, and the team's capacity to operate GPU infrastructure.

### Data-Handling Boundary

Qwen inference runs in team-managed infrastructure (the k3s cluster and GPU node described in Section 4). GPT-4o-mini requests are sent to an external API operated by OpenAI. This is a description of where inference executes, not a privacy assessment: the benchmark did not test network egress, data residency, retention terms, or regulatory requirements, so this report makes no claim of compliance, data sovereignty, or complete privacy for either path. Any use with sensitive content would need a separate review of the applicable policies and provider terms.

## 11. Live Service Demonstration

The deployed service was demonstrated via the live endpoint at **http://10.0.0.15:30801**. The demonstration covered uploading .ipynb files via **POST /v1/tag/upload** with both **model=qwen** and **model=openai**, comparing TagResult JSON responses side by side, and running the concurrent benchmark (3 users, 3 files) while observing batching behaviour live on the Grafana dashboard at **https://t08-graf.aidc.nadir.sh**.

The Streamlit interface provides file upload, model selection and structured-result review. Demonstration checks also include GET /health, GET /v1/models and GET /metrics. These are the recorded lab endpoints and do not establish continuing public availability. [S2, S4]

**AI Hub scope:** AI Hub deployment was optional for the final presentation and was deferred until after the presentation based on instructor guidance reported by the team. The completed demonstration is a live CTCM service demonstration. [S6]

## 12. Live Observability

The following observations come from the CTCM-Prometheus Grafana record for 27-28 September 2026 and the final SLO record for 28 September (UTC+3). They describe their captured windows, not a single continuous production measurement. Application metrics cover both model paths; native vLLM metrics cover Qwen only. Executable PromQL examples appear in Appendix B. [S3, S5]

### 12.1 Service availability

Availability was high during normal operation but temporarily decreased during pod restart/deployment activity. The final SLO record reports **94.2%** in one recent one-hour window, below the proposed **99%** target. Earlier captures showed values from approximately 87% to 100%; these are separate observations. Prometheus **up** measures scrape reachability and does not by itself prove successful user requests.

### 12.2 Qwen requests and request rate

The original dashboard record reports **29 successful Qwen requests** in a 12-hour window on 28 September. Request counts reflect the selected labels and window; they are not the 12-file benchmark sample size. Successful Qwen request rate peaked at approximately **1.80 requests/minute** in a one-minute query window, with OpenAI activity visible in the same panel. [S5]

### 12.3 Concurrent requests on the GPU

The running-request metric reached **3 simultaneous Qwen inference requests**. Together with successful client requests and vLLM runtime evidence, this supports active concurrent inference through AsyncLLMEngine. It does not establish the service's maximum sustainable concurrency. [S2, S3]

### 12.4 Full-pipeline E2E latency

The dashboard record showed Qwen p50 reaching approximately **2.50 minutes** under peak concurrent load. The final SLO record describes p95 approaching approximately **3 minutes**. The final sequential mean was **56.39 s** for Qwen and **71.98 s** for GPT-4o-mini. Means, percentiles, model-specific series and measurement windows must be kept distinct.

Higher E2E latency under load is consistent with waiting and shared-resource contention, but these observations do not isolate one cause. A rounded p95 near 180 seconds is insufficient to confirm compliance with a ≤180 s objective for each model.

### 12.5 TTFT and TPOT

Qwen's vLLM panels expose time to first token (TTFT) and time per output token (TPOT). The captured TPOT p95 was approximately **61.9 ms/token**, with p50 around **38-40 ms/token** during lighter load. These are engine diagnostics, not full-pipeline latency. No comparable provider-side GPT-4o-mini TTFT/TPOT measurements were captured, and the final benchmark CSV does not contain these metrics.

### 12.6 Qwen request queue time

The original dashboard record showed p95 queue time reaching approximately **60 seconds** during concurrent traffic and remaining near zero at low load. This demonstrates waiting inside the serving engine during the captured period. It does not mean the complete application workload was executed serially.

### 12.7 Prompt and generation throughput

Prompt-processing throughput reached approximately **534 prompt tokens/second** during concurrent Qwen activity. The panel also displayed generation throughput. Prompt throughput and output generation speed measure different work and must not be compared as if they were the same metric. The running-request metric is the direct evidence of simultaneously active inference requests.

### 12.8 Process virtual memory

The recorded process virtual-memory range was approximately **65-75 GiB**, including a tooltip around **66.5 GiB**. The query divides bytes by 1024³, so GiB is the correct unit. Virtual address space includes mapped files, shared libraries and reservations; it must not be interpreted as physical RAM consumption. Apparent stability in a short capture does not rule out a memory leak.

### 12.9 Request error rate

The final SLO record reports **0% application error rate** in its latest dashboard observation. Separately, the final concurrent benchmark completed **9/9 Qwen requests and 9/9 OpenAI requests successfully**. These support zero observed failures in that test, not a long-term reliability guarantee.

An empty graph or a query that replaces missing series with zero does not establish a measured 0% error rate. Error-rate interpretation requires available counters and nonzero request traffic in the same window. Earlier development failures are outside the final-run result. [S3, S5]

> **Measurement boundaries**
>
> **Application layer:** reachability, request outcomes, E2E latency and successful throughput.  
> **Qwen engine layer:** active and waiting requests, TTFT, TPOT, queue time, KV-cache and token throughput.  
> **Offline evaluation:** tags, difficulty, skills, retrieval recall and output validity.

The distinction between latency measures is summarized below. Only the Qwen path exposes vLLM/GPU-native metrics; OpenAI provider-side inference internals are not observable by the team.

| Measure | Scope | Available for |
| --- | --- | --- |
| Client E2E latency | Full client-observed request (extraction, retrieval, inference, response) | Qwen and OpenAI |
| Application histogram latency | Full pipeline as recorded by the service's request histogram | Qwen and OpenAI |
| Model / inference latency | Separately recorded inference timer; basis of reported tok/s | Qwen and OpenAI (as recorded by the application) |
| Generation speed (tok/s) | Completion tokens / inference latency; not isolated decode speed | Qwen and OpenAI (as recorded by the application) |
| TTFT, TPOT, queue time | vLLM engine internals | Qwen only |

The custom request histogram uses buckets at 1, 2.5, 5, 10, 20, 30, 60, 120, 180, 300 and 600 seconds. The 180-second boundary supports the proposed latency objective; short windows and low request counts still limit percentile interpretation. [S4]

## 13. Lessons Learned

A standardised evaluation process - same dataset, prompt structure, 3-pass inference pipeline, output schema, and scoring framework - was essential for a fair comparison.

### Asynchronous serving enables concurrency

The async upload endpoint and awaited Qwen call enabled concurrent requests to reach vLLM. The final concurrent run is the performance reference: Qwen completed 9/9 requests with **1.24x workload speedup** and **3 active inference requests**. Differences between runs should not be attributed solely to one code change, and intermediate validation runs made after the async change are not part of the final comparison.

### Instrument the quantity being claimed

The client E2E timer, application histogram and internal inference timer answer different questions. Histogram buckets that include long requests are necessary for meaningful latency panels. Generation speed, prompt throughput, queue time and E2E latency must retain their own units and scopes.

### Retrieval is not final skill selection

Both models achieved **86.1% pool recall**, while final skill-mapping accuracy was lower and differed between models. Retrieval can supply relevant candidates without guaranteeing correct final selection. The recorded results do not include a controlled ablation proving that Pass 2 retrieval outperforms Pass 1 retrieval.

### Startup behavior needs production validation

The development record describes PRELOAD_QWEN=false as a workaround for an asyncio event-loop conflict. Production initialization should use the serving event loop, expose readiness after successful initialization, and pass startup and restart tests. A background task alone is not evidence of a completed fix. [S5]

### Service objectives need explicit evidence

The final run supports successful short-workload concurrency and throughput. Availability did not meet its target in the reported one-hour window, and rounded p95 observations do not settle per-model compliance. The exported cost estimates require reconciliation with the code path and actual provider charges.

### Final assessment

CTCM combines multi-format extraction, RAG, local and API inference, Docker, Kubernetes, FastAPI, Prometheus, Grafana and Streamlit. GPT-4o-mini showed stronger results in tagging and difficulty; Qwen showed advantages in skill mapping and final sequential E2E latency. Both pass the benchmark validity checks and complete the final concurrent workload successfully.

Model selection should weigh quality, E2E latency, throughput, validated cost, observability and operating responsibility. The 12-file dataset and 9-request concurrent runs demonstrate the capstone use case; they do not establish production capacity or long-term SLO compliance.

## 14. Optional Future Work

The following items are **future proposals only**. None of them was implemented or benchmarked in this project, and no result in this report depends on them.

1. **Intelligent model routing.** Explore routing requests between local Qwen and an external API model, for example by file type, file size or current load. Any routing rule would need its own evaluation of quality, latency, cost and data-handling implications before adoption.
2. **Multi-GPU / multi-worker scaling.** Investigate whether additional workers, replicas or GPUs improve throughput and tail latency beyond the single-replica, single-GPU, one-Uvicorn-worker setup tested here. Scaling behavior beyond 3 concurrent requests was not measured.
3. **Queue-depth signals for autoscaling.** Evaluate vLLM queue-depth or waiting-request metrics as possible signals for future autoscaling decisions. This report observed running requests and queue time only; it does not show that such a signal would be reliable.
4. **Human-in-the-loop curriculum review.** Consider a review step in the Streamlit interface where reviewers can accept or adjust predicted tags and competency mappings. The workflow, reviewer qualifications and audit trail would need to be defined first.

## Appendix A - Service Indicators & Proposed SLOs

Source of targets: **observability/slo-targets.md**. These are provisional capstone objectives. Service: CTCM /v1/tag/upload in namespace ctcm. Measurement date: **28 September 2026 (UTC+3)**. [S3]

| Indicator & target | Window / observed evidence | Assessment |
| --- | --- | --- |
| **Availability ≥99%**<br>Service scrape reachability | 1-hour query during scheduled service.<br>**94.2%** in the reported restart/deployment-affected window. | **Not met** in that window. |
| **p95 E2E latency ≤180 s**<br>Per model | 5-minute histogram/rate window during active traffic.<br>p95 approached approximately 3 minutes. | **Insufficient evidence** for exact per-model compliance. |
| **Successful throughput ≥50 files/hour/model** | 5-minute rate window; complete-run benchmark also used.<br>Qwen **89/hr**; OpenAI **100/hr**. | **Met** for the measured concurrent runs. |
| **Request error rate ≤1%** | 5-minute rate window during active service.<br>Latest record: 0%; final concurrency: **0/9 failures per model**. | **Met** for the observed test; limited sample. |
| **Qwen concurrency ≥3**<br>Without request failure | Active concurrent test.<br>**3** active vLLM requests; **9/9** successful client requests. | **Demonstrated** for the tested workload. |

### How the targets are applied

- **Availability** covers scheduled service windows, not 24/7 operation. Scrape reachability is a service-level indicator shared by both model paths, not a measurement of OpenAI provider availability.

- **Latency** is evaluated separately for each model. A sequential average cannot substitute for p95 under concurrent traffic.

- **Throughput** is workload-specific. The three-file concurrent workload differs from the 12-file evaluation set.

- **Error rate** needs real request traffic and available telemetry; an empty graph cannot be counted as success.

- **Concurrency** demonstrates support for three active Qwen requests; it does not establish maximum capacity.

The historical readiness check's <10 s average-latency threshold and the previous appendix's model-specific mean-latency thresholds are not the final SLO. Quality scores (including skill mapping and RAG pool recall) remain offline benchmark results; they are not extra service targets in this final SLO set.

## Appendix B - Prometheus Query Reference

Executable reference expressions for the recorded metrics. These normalize the original shorthand; they are not a claim that the deployed dashboard JSON was modified. Use a single percentile per expression. [S3-S5]

**Service availability - percent, 1 hour**

```promql
100 * avg_over_time(up{job="content-tagging"}[1h])
```

**Successful Qwen requests - 12-hour observation**

```promql
sum(increase(model_requests_total{model="qwen",
  status="success"}[12h]))
```

**Active Qwen inference requests**

```promql
vllm:num_requests_running{model_name=~".*Qwen.*"}
```

**Successful requests/minute by model - SLO rate window**

```promql
60 * sum by (model) (rate(model_requests_total{
  model=~"qwen|openai",status="success"}[5m]))
```

**Full-pipeline p95 E2E latency - seconds, per model**

```promql
histogram_quantile(0.95, sum by (le, model) (
  rate(model_request_duration_seconds_bucket{
    model=~"qwen|openai"}[5m])))
```

**Qwen p95 TPOT - milliseconds/token**

```promql
1000 * histogram_quantile(0.95, sum by (le) (
  rate(vllm:time_per_output_token_seconds_bucket{
    model_name=~".*Qwen.*"}[5m])))
```

**Qwen p95 queue time - seconds**

```promql
histogram_quantile(0.95, sum by (le) (
  rate(vllm:request_queue_time_seconds_bucket{
    model_name=~".*Qwen.*"}[5m])))
```

**Qwen prompt-processing throughput - tokens/second**

```promql
sum(rate(vllm:prompt_tokens_total{
  model_name=~".*Qwen.*"}[1m]))
```

**Process virtual address space - GiB**

```promql
process_virtual_memory_bytes{job="content-tagging"}
  / 1024 / 1024 / 1024
```

For p50, replace 0.95 with 0.50. The captured request-rate peak used a 1-minute query; the SLO record specifies a 5-minute rate window. Query scopes should remain restricted to the intended CTCM deployment.

## Appendix C - Evidence, Reproducibility & Revision Record

### Error rate: evaluate only with valid traffic

```promql
100 * (sum(rate(model_requests_total{status="error"}[5m]))
  or vector(0)) /
clamp_min(sum(rate(model_requests_total[5m]))
  or vector(0), 0.000000001)
```

This reproduces the dashboard's zero-fallback approach. The query can display zero when telemetry is missing or traffic is absent. Confirm a healthy scrape target and a positive total request rate before interpreting the result; otherwise report no traffic or insufficient data.

### Concurrent test evidence captures

The two captures below are the per-model console outputs behind Figure 1. [S7]

![Qwen concurrent benchmark console output: 3 users x 3 files](../docs/images/concurrent-qwen.png)

*Figure C1. Qwen: baseline 149.2 s (avg 49.7 s/file); concurrent wall time 362.3 s; average latency 120.8 s/file; speedup 1.24x; 89 files/hr; 9/9 OK.*

![OpenAI concurrent benchmark console output: 3 users x 3 files](../docs/images/concurrent-openai.png)

*Figure C2. OpenAI (GPT-4o-mini): baseline 125.6 s (avg 41.9 s/file); concurrent wall time 324.4 s; average latency 108.1 s/file; speedup 1.16x; 100 files/hr; 9/9 OK.*

Per-file latencies read from the captures (seconds):

| File | Qwen baseline | Qwen concurrent (users 1-3) | OpenAI baseline | OpenAI concurrent (users 1-3) |
| --- | --- | --- | --- | --- |
| Pandas Basics | 38.8 | 92.4 / 92.4 / 92.4 | 31.4 | 76.7 / 77.5 / 77.2 |
| Decision Trees | 58.7 | 138.0 / 138.0 / 138.0 | 49.6 | 132.9 / 133.1 / 134.3 |
| ML Workflow | 51.6 | 131.9 / 131.9 / 131.9 | 44.6 | 114.8 / 113.8 / 112.9 |

Displayed per-file values are rounded, so their sums can differ from the reported totals by about 0.1 s (for example, the Qwen baseline files sum to 149.1 s versus the reported 149.2 s). The screenshots reproduce printed console output; the raw per-request logs and timestamps should be retained for audit.

### Source register

| ID | Evidence used |
| --- | --- |
| [S1] | **results_final/**: benchmark_summary.csv, all_results.csv, openai_results.csv and qwen_results.csv in the supplied repository snapshot. Canonical 12-file comparison. |
| [S2] | **Final README** (29 September 2026) and **evaluation/concurrent_benchmark.py**: final concurrent values, client-timing method, workload and batching evidence references. |
| [S3] | **observability/slo-targets.md**: final five service indicators, targets, measurement windows and observations. |
| [S4] | **Repository configuration and code**: app/config.py, main.py, scorer.py, schemas.py, model modules, prompts.py and k8s/ manifests. Used for deployment, output-contract and measurement definitions. |
| [S5] | **benchmark_report_pre-final.pdf** and exported Grafana dashboard: original narrative, recorded observations and queries. Numeric captures are reproduced as historical observations, not newly measured telemetry. |
| [S6] | **Team-provided instructor guidance** in the supplied conversation: AI Hub optional for the final presentation and deferred until afterward. |
| [S7] | **Console captures** in docs/images/: concurrent-benchmark-summary.png, concurrent-qwen.png, concurrent-openai.png (output of evaluation/concurrent_benchmark.py) and concurrent-requests-validation.png (live three-request check). Screenshots of printed output, not raw logs. |

### Revision record

Retained the correct project overview, use case, model descriptions, deployment configuration, Golden Set process, quality results and task-performance analysis. Updated the final sequential and concurrent values, all dependent comparisons, observability interpretations, Live Service Demonstration title and final five-target SLO appendix.

Added measurement and cost qualifications where the source code required them. Intermediate after-fix results are no longer substituted into the final comparison. Missing provider metrics and uncertain SLO conclusions are identified explicitly.

**Latest revision (29 September 2026).** Added the intended output contract with an explicit statement of what the validity metric does and does not check; a Data-Handling Boundary paragraph; an Optional Future Work section labelled as proposals only; a latency-measure summary table; and the concurrent-test evidence captures with per-file timings. Comparison wording was made neutral (no overall winner). A secondary draft was reviewed for wording and context only; its intermediate after-fix and older concurrency values, its earlier mean-latency SLO thresholds and PASS marking for availability, and its data-sovereignty, zero-egress, cost-reduction, "eliminated hallucinations" and production-readiness claims were not adopted because the final sources do not support them.

**Reproduction:** run evaluation/run_benchmark.py against the same 12 files and reviewed Golden Set; run evaluation/concurrent_benchmark.py for the three-user workload. Retain per-request results, exact timestamps, configuration and dashboard exports alongside results_final/.
