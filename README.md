# Content Tagging & Competency Mapping (CTCM)

**Team 2 — AI Data Center Operations Capstone**

CTCM is an AI-powered service that analyzes learning content and automatically generates structured educational metadata for content tagging and competency mapping.

The service produces:

- Content summaries
- Topic tags
- Difficulty levels
- Competency / skill mappings
- Confidence scores
- Three learning objectives

The project combines **multimodal content extraction, RAG, local GPU inference, OpenAI inference, vLLM continuous batching, Docker, Kubernetes, Prometheus, Grafana, and Streamlit** in one end-to-end AI system.

---

## Demo

### Streamlit Application

The Streamlit interface allows users to upload learning content, select an inference backend, and inspect the generated tagging and competency-mapping results.

<p align="center">
  <img src="docs/gifs/streamlit-demo.gif"
       alt="CTCM Streamlit Demo"
       width="1000">
</p>

---

## System Architecture

```text
Learning Content
PPTX / PDF / XLSX / IPYNB / Images / Code / Text
        |
        v
Content Extraction
Text + Images + OCR
        |
        v
Digest / Preprocessing
        |
        +-----------------------------+
        |                             |
        v                             v
Qwen + vLLM                     OpenAI API
AsyncLLMEngine                  gpt-4o-mini
Local NVIDIA GPU                External API
        |                             |
        +--------------+--------------+
                       |
                       v
                3-Pass Pipeline
        1. Tags + initial skills
        2. RAG skill refinement
        3. Difficulty refinement
                       |
                       v
             Structured API Response
                       |
          +------------+-------------+
          |                          |
          v                          v
      Streamlit              Prometheus / Grafana
```

---

## Model Backends

| Backend | Model | Serving |
|---|---|---|
| **Qwen** | `Qwen/Qwen2.5-VL-3B-Instruct-AWQ` | Local GPU using vLLM |
| **OpenAI** | `gpt-4o-mini` | OpenAI API |

The local Qwen backend uses vLLM `AsyncLLMEngine`, enabling:

- Continuous batching
- Paged attention
- Asynchronous generation
- Concurrent request processing

The capstone deployment was tested on an **NVIDIA RTX A6000**.

---

## Inference Pipeline

### Pass 1 — Content Analysis

The model generates:

- Content summary
- Predicted topic tags
- Initial skill predictions

### Pass 2 — RAG Skill Refinement

The service retrieves relevant competencies from the skill taxonomy using the extracted learning content and first-pass tags.

- Embedding model: `BAAI/bge-m3`
- Skill taxonomy: **136 skills**
- Retrieval pool: **Top 15 candidate skills**

The model then selects its final competency mappings from the retrieved skill pool.

### Pass 3 — Difficulty Refinement

A focused inference pass classifies the learning content as:

- Beginner
- Intermediate
- Advanced

---

## Structured Output

A successful request returns structured output similar to:

```json
{
  "content_summary": "...",
  "predicted_tags": [
    "...",
    "..."
  ],
  "difficulty_level": "Intermediate",
  "predicted_skills": [
    "...",
    "...",
    "...",
    "..."
  ],
  "confidence": 0.90,
  "notes": "Identify ... • Apply ... • Evaluate ..."
}
```

The service is designed to return:

- Exactly **four competency mappings**
- Exactly **three learning objectives** in the `notes` field

Skill outputs are grounded against the defined competency taxonomy.

---

## Supported Content Types

The extraction pipeline supports multiple learning-content formats, including:

- PowerPoint
- PDF
- Word documents
- Excel / CSV / TSV
- Jupyter notebooks
- Markdown and plain text
- HTML
- Source-code files
- Images
- ZIP archives

OCR support is included for image-based or scanned content.

---

## Evaluation Dataset & Methodology

The final benchmark used:

- **12 representative learning-content files**
- A reviewed Golden Set
- The same task and output schema for both model backends
- The same evaluation and scoring methodology
- RAG-based skill grounding
- Structured-output validation
- Quality, latency, token, cost, and throughput measurements

The benchmark compares each model output against the reviewed reference data.

The evaluation covers:

- Tagging / classification quality
- Skill-mapping accuracy
- Retrieval quality
- Difficulty classification
- Structured-output validity
- End-to-end latency
- Generation speed
- Token usage
- Estimated cost
- Throughput
- Concurrent request behavior

The canonical final benchmark outputs are stored in:

```text
results_final/
```

---

## Final Benchmark Results

<p align="center">
  <img src="docs/images/benchmark-performance-accuracy-summary.png"
       alt="CTCM Final Benchmark Performance and Accuracy"
       width="100%">
</p>

| Metric | Qwen | OpenAI |
|---|---:|---:|
| Tagging / Classification Accuracy | **41.8%** | **50.1%** |
| Skill Mapping Accuracy | **27.0%** | **24.5%** |
| Retrieval Quality | **86.1%** | **86.1%** |
| Structured Output Validity | **100%** | **100%** |
| Difficulty Accuracy | **66.7%** | **83.3%** |
| Tag Semantic F1 | **43.4%** | **53.4%** |
| Average E2E Latency | **56.39 s** | **71.98 s** |
| Generation Speed | **29.16 tok/s** | **105.67 tok/s** |
| Total Tokens — 12 files | **107,195** | **287,621** |
| Estimated Cost — 12 files | **$0.0575** | **$0.0746** |
| Estimated Cost / 1,000 Files | **$4.79** | **$6.22** |
| Estimated Throughput | **63.8 files/hr** | **50.0 files/hr** |

These measurements are specific to the capstone benchmark workload and test environment.

<details>
<summary><strong>View full benchmark execution</strong></summary>

<br>

<p align="center">
  <img src="docs/images/full-benchmark-test.png"
       alt="Full Benchmark Execution"
       width="100%">
</p>

</details>

---

## Benchmark Findings & Trade-offs

The two inference backends showed different strengths.

**GPT-4o-mini** achieved stronger results in several content-quality measures:

- Higher tagging / classification accuracy
- Higher semantic tag F1
- Higher difficulty-classification accuracy
- Higher generation speed

However, it relies on an external API and therefore provides less infrastructure control.

**Qwen** demonstrated advantages in several operational areas:

- Higher skill-mapping accuracy in the final benchmark
- Lower average end-to-end latency
- Lower total token usage
- Lower estimated cost
- Higher estimated benchmark throughput
- Full control over local deployment and inference infrastructure

The local Qwen deployment requires additional operational responsibility, including GPU capacity, model serving, Docker, Kubernetes, monitoring, and scaling.

The benchmark therefore demonstrates that model selection depends on the priorities of the use case rather than a single performance metric.

---

## Concurrent Benchmark

Concurrency was evaluated with:

- **3 simultaneous users**
- **3 representative learning files**
- Both Qwen and OpenAI
- **9 requests per model**

<p align="center">
  <img src="docs/images/concurrent-benchmark-summary.png"
       alt="Concurrent Benchmark Summary"
       width="900">
</p>

| Metric | Qwen | OpenAI |
|---|---:|---:|
| Successful Requests | **9/9** | **9/9** |
| Sequential Baseline | 149.2 s | 125.6 s |
| Concurrent Wall Time | 362.3 s | 324.4 s |
| Average Latency / File | 120.8 s | 108.1 s |
| Workload Speedup | **1.24x** | **1.16x** |
| Throughput | **89 files/hr** | **100 files/hr** |

Both model paths completed all concurrent requests successfully.

The test also demonstrates an important trade-off: concurrent workloads improve total workload throughput, while individual request latency increases under load.

<details>
<summary><strong>Qwen concurrent benchmark details</strong></summary>

<br>

<p align="center">
  <img src="docs/images/concurrent-qwen.png"
       alt="Qwen Concurrent Benchmark"
       width="850">
</p>

</details>

<details>
<summary><strong>OpenAI concurrent benchmark details</strong></summary>

<br>

<p align="center">
  <img src="docs/images/concurrent-openai.png"
       alt="OpenAI Concurrent Benchmark"
       width="850">
</p>

</details>

---

## Qwen Continuous Batching

Qwen is served through vLLM `AsyncLLMEngine`.

Three Qwen requests were launched simultaneously:

<p align="center">
  <img src="docs/images/concurrent-requests-validation.png"
       alt="Three Concurrent Qwen Requests"
       width="900">
</p>

All three requests completed successfully.

During the concurrent workload, the vLLM runtime reported:

```text
Running: 3 reqs
Pending: 0 reqs
```

<p align="center">
  <img src="docs/images/vllm-continuous-batching-evidence.png"
       alt="vLLM Continuous Batching Evidence"
       width="100%">
</p>

Prometheus also recorded three simultaneously running Qwen inference requests:

<p align="center">
  <img src="docs/images/qwen-running-requests-grafana.png"
       alt="Qwen vLLM Concurrent Requests"
       width="1000">
</p>

This provides runtime evidence that multiple Qwen inference requests were active in the vLLM engine at the same time.

Individual application stages inside a request may still execute sequentially, while vLLM performs continuous batching across concurrent inference requests.

---

## Docker

The GPU container is defined in:

```text
docker/Dockerfile
```

Build:

```bash
docker build \
  -f docker/Dockerfile \
  -t noura93/content-tagging:gpu-v1 \
  .
```

Push:

```bash
docker push noura93/content-tagging:gpu-v1
```

<details>
<summary><strong>Docker build and push evidence</strong></summary>

<br>

<p align="center">
  <img src="docs/images/docker-build-and-push.png"
       alt="Docker Build and Push"
       width="900">
</p>

</details>

---

## Kubernetes Deployment

The CTCM service was deployed on Kubernetes together with Prometheus and Grafana in the `ctcm` namespace.

Kubernetes manifests are stored under:

```text
k8s/
```

They include:

```text
namespace.yaml
deployment.yaml
service.yaml
pvc.yaml
prometheus.yaml
grafana.yaml
secret.yaml
```

### Deploy

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/prometheus.yaml
kubectl apply -f k8s/grafana.yaml
```

### Deployment Evidence

The application and observability workloads were verified running successfully in the `ctcm` namespace.

<p align="center">
  <img src="docs/images/kubernetes-pods-running.png"
       alt="CTCM Kubernetes Pods Running"
       width="1000">
</p>

### Lab NodePorts

| Service | NodePort |
|---|---:|
| CTCM API | `30801` |
| Grafana | `30301` |
| Prometheus | `30900` |

---

## API

The backend is implemented with **FastAPI**.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Service health and loaded models |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/v1/models` | Available model backends |
| `POST` | `/v1/tag/upload` | Upload and analyze one file |
| `POST` | `/v1/tag` | Analyze content through JSON input |
| `POST` | `/v1/benchmark` | Run benchmark comparison |
| `GET` | `/v1/benchmark/summary` | Benchmark metric definitions |

Example:

```bash
curl -X POST http://<HOST>:8000/v1/tag/upload \
  -F "file=@data/Lecture - Pandas Basics.ipynb" \
  -F "model=qwen"
```

Available model values:

```text
qwen
openai
```

---

## Observability

The project uses:

- **Prometheus** for metric collection
- **Grafana** for dashboard visualization
- Application-level metrics for both model paths
- vLLM-native inference metrics for Qwen

### Grafana Dashboard

<p align="center">
  <img src="docs/gifs/grafana-dashboard-demo.gif"
       alt="CTCM Grafana Observability Dashboard"
       width="1000">
</p>

The dashboard includes panels for:

- Service availability
- Qwen request activity
- OpenAI request activity
- Error rate
- End-to-end latency
- Request throughput
- Concurrent Qwen GPU requests
- GPU KV-cache utilization
- TTFT
- TPOT
- Queue time
- Prompt and generation throughput
- Token usage
- Process memory

### Application Metrics

Examples:

```text
model_requests_total{model="qwen",status="success"}
model_requests_total{model="openai",status="success"}

model_request_duration_seconds{model="qwen"}
model_request_duration_seconds{model="openai"}
```

These metrics are labeled by model, allowing Qwen and OpenAI requests to be monitored separately.

### Qwen / vLLM Metrics

The local Qwen backend exposes metrics including:

- Requests running
- Requests waiting
- GPU KV-cache utilization
- Time to First Token (TTFT)
- Time per Output Token (TPOT)
- Queue time
- Prompt throughput
- Generation throughput
- Prefill / decode behavior

vLLM and GPU metrics apply only to **Qwen**, because OpenAI inference is handled through an external API.

### Qwen vs OpenAI Request Rate

<p align="center">
  <img src="docs/images/request-rate-qwen-openai.png"
       alt="Qwen vs OpenAI Request Rate"
       width="1000">
</p>

The final exported Grafana dashboard is stored in:

```text
observability/CTCM — Infrastructure & Inference Benchmark Dashboard.json
```

---

## Service Indicators & Proposed Targets

The project's measured service indicators and proposed objectives are documented in:

```text
observability/slo-targets.md
```

| Indicator | Proposed Target |
|---|---:|
| Scheduled-window Availability | `>= 99%` |
| Request Error Rate | `<= 1%` |
| E2E p95 Latency | `<= 180 s` per model |
| Successful Throughput | `>= 50 files/hour/model` |
| Qwen Concurrency | `>= 3 simultaneous requests` |

These are provisional objectives based on the measured capstone workload and are not production commitments.

---

## Streamlit Application

The interactive evaluation/demo interface is stored under:

```text
demo/
```

Install:

```bash
cd demo
pip install -r requirements.txt
```

Run:

```bash
streamlit run streamlit_app.py
```

Additional documentation is available in:

```text
demo/README_streamlit_demo.md
```

---

## Benchmark Report

Detailed benchmark methodology, analysis, model trade-offs, and conclusions are documented in:

```text
reports/benchmark_report.md
```

The README provides a concise project overview, while the benchmark report contains the detailed evaluation analysis.

---

## AI Hub Scope

> AI Hub deployment was optional for the final presentation and was deferred until after the presentation based on instructor guidance.

The final capstone work therefore focuses on the implemented model deployment, evaluation, benchmarking, observability, concurrency testing, and demonstration interface.

---

## Local Setup

### Clone

```bash
git clone https://github.com/Noura93a/AIDC-CTCM-Team2.git
cd AIDC-CTCM-Team2
```

### Create Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install torch==2.5.1 \
  --index-url https://download.pytorch.org/whl/cu121

pip install -r app/requirements.txt
```

### Environment Variables

```bash
export OPENAI_API_KEY="<your-openai-api-key>"
export OPENAI_MODEL="gpt-4o-mini"

export SKILLS_CSV_PATH="$PWD/data/hrsd_data_ai_taxonomy.csv"
export GOLD_SET_PATH="$PWD/data/Golden-set-Reviewed.xlsx"
```

> Never commit a real API key, token, password, or credential to the repository.

### Start the API

```bash
cd app

uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1
```

Health check:

```bash
curl http://localhost:8000/health
```

---

## Run the Benchmarks

### Full Benchmark

```bash
python evaluation/run_benchmark.py \
  --server http://<HOST>:8000 \
  --data-dir ./data \
  --gold ./data/Golden-set-Reviewed.xlsx \
  --models openai,qwen \
  --out ./results_final
```

### Concurrent Benchmark

```bash
python evaluation/concurrent_benchmark.py
```

---

## Repository Structure

```text
AIDC-CTCM-Team2/
├── app/                  # API, extraction, inference, RAG and scoring
├── data/                 # Golden Set, taxonomy and benchmark content
├── demo/                 # Streamlit evaluation/demo application
├── docker/               # GPU Docker image
├── docs/
│   ├── images/           # Benchmark and deployment evidence
│   └── gifs/             # Streamlit and Grafana demo GIFs
├── evaluation/           # Full and concurrent benchmark scripts
├── k8s/                  # Kubernetes deployment and monitoring manifests
├── observability/        # Grafana dashboard and SLI/SLO documentation
├── reports/              # Detailed benchmark report
├── results_final/        # Canonical final benchmark outputs
└── README.md
```

---

## Additional Evidence

<details>
<summary><strong>Deployment readiness check</strong></summary>

<br>

<p align="center">
  <img src="docs/images/deployment-readiness-check.png"
       alt="Deployment Readiness Check"
       width="900">
</p>

The readiness script used strict development thresholds. Its historical `< 10 s` average-latency threshold is different from the final capstone SLO documented in `observability/slo-targets.md`.

</details>

<details>
<summary><strong>Smoke test — both models</strong></summary>

<br>

<p align="center">
  <img src="docs/images/smoke-test-both-models.png"
       alt="Smoke Test Both Models"
       width="100%">
</p>

</details>

---

## Technologies

- Python 3.11
- FastAPI
- PyTorch
- vLLM
- Hugging Face Transformers
- Qwen2.5-VL
- OpenAI API
- BGE-M3
- Docker
- Kubernetes / k3s
- NVIDIA CUDA
- Prometheus
- Grafana
- Streamlit
- Pandas

---

## Security

Do not commit:

- OpenAI API keys
- GitHub PATs
- Passwords
- Private tokens
- Local credentials

Keep the repository version of `k8s/secret.yaml` empty or placeholder-only and inject real secrets at deployment time.

---

## Team

**Team 2 — AI Data Center Operations Capstone**

**Content Tagging & Competency Mapping (CTCM)**
