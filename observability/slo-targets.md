# Service indicators and proposed targets

Team: Team 2

Use case: Content Tagging & Competency Mapping. The service analyzes learning content for tagging, difficulty estimation, and competency/skill mapping.

Service measured: CTCM team service, endpoint `/v1/tag/upload`, namespace `ctcm`. The service supports Qwen (`Qwen/Qwen2.5-VL-3B-Instruct-AWQ`) through local vLLM inference on the NVIDIA A6000 GPU, and OpenAI (`gpt-4o-mini`) through the external OpenAI API.

Workload: Final benchmark and concurrent benchmark using representative learning-content files. The concurrent test used 3 users across 3 files for each model. Qwen completed 9/9 concurrent requests and OpenAI completed 9/9 concurrent requests.

Measurement period: 2026-09-28 (UTC+3), covering the final benchmark, concurrent benchmark, and corresponding Grafana/Prometheus observation windows.

Instrumentation gaps: Application-level request, latency, throughput, and error metrics are available for both models. vLLM/GPU metrics such as TTFT, TPOT, queue time, KV-cache usage, and GPU concurrency apply only to Qwen. Model-quality metrics are evaluated offline from the final benchmark.

## SLI 1

Indicator: Service availability, measuring the percentage of recorded Prometheus scrapes in which the CTCM service was reachable.

Panel: Service Availability %

Unit: percent

Target: >= 99% availability during scheduled service and benchmark windows.

Window: 1 hour Prometheus query window. The objective applies to scheduled service periods rather than 24/7 availability because the capstone environment is not continuously operated.

Observed: The dashboard showed 94.2% during one recent one-hour window affected by service restart/deployment activity.

Evidence: Grafana `Service Availability %` panel using `up{job="content-tagging"}`.

Why it fits: Availability measures whether the tagging service is reachable and able to expose its application and monitoring endpoints when the team is operating the system.

Limitations: The environment is a capstone/test environment rather than a continuously running production service. Planned pod restarts, deployments, and GPU/server availability can reduce the measured percentage. Prometheus `up` measures scrape reachability of the service metrics endpoint; it does not by itself prove that every user request succeeds.

## SLI 2

Indicator: p95 end-to-end request latency for the complete tagging pipeline, measured separately for Qwen and OpenAI.

Panel: E2E Latency — Qwen vs OpenAI p50 / p95 (full pipeline)

Unit: seconds

Target: <= 180 seconds p95 E2E latency per model during the tested workload.

Window: 5 minute Prometheus histogram/rate window, evaluated during active benchmark traffic.

Observed: Grafana showed p95 full-pipeline latency reaching approximately 3 minutes during concurrent load. In the final benchmark, average E2E latency was 56.39 seconds for Qwen and 71.98 seconds for OpenAI. In the concurrent benchmark, average latency per file was 120.8 seconds for Qwen and 108.1 seconds for OpenAI.

Evidence: Grafana `E2E Latency — Qwen vs OpenAI p50 / p95 (full pipeline)` panel using `model_request_duration_seconds`, together with the final and concurrent benchmark results.

Why it fits: End-to-end latency represents the actual time a user waits for the complete tagging and competency-mapping response, including extraction, model inference, RAG/skill mapping, and response construction.

Limitations: The target is provisional and is based on a short capstone benchmark. Latency increases under concurrency, and OpenAI latency also depends on an external API. Longer production-representative testing would be needed to establish a production SLO.

## SLI 3

Indicator: Successful request throughput per model.

Panel: Request Rate — Qwen vs OpenAI (req/min)

Unit: requests/minute and files/hour

Target: >= 50 successful files/hour per model during the tested workload.

Window: 5 minute Prometheus rate window; benchmark throughput is also calculated over the complete concurrent run.

Observed: Qwen achieved 89 files/hour in the concurrent benchmark. OpenAI achieved 100 files/hour. Both models exceeded the proposed target.

Evidence: Grafana `Request Rate — Qwen vs OpenAI (req/min)` panel using `model_requests_total`, together with the concurrent benchmark summary.

Why it fits: Throughput measures how much useful tagging work the system completes over time and shows whether the service can sustain work from multiple users.

Limitations: Throughput depends on file size, content complexity, model behavior, external OpenAI API conditions, and the capacity of the single local GPU. The test used three representative files and three concurrent users.

## SLI 4

Indicator: Percentage of model requests that fail.

Panel: Error Rate % (All Models)

Unit: percent

Target: <= 1% request error rate during the active service window.

Window: 5 minute Prometheus rate window.

Observed: The latest dashboard observation showed 0% error rate. The final concurrent benchmark completed 9/9 Qwen requests and 9/9 OpenAI requests successfully.

Evidence: Grafana `Error Rate % (All Models)` panel using `model_requests_total{status="error"}`, together with the concurrent benchmark success results.

Why it fits: A tagging service must return successful responses consistently. Error rate provides a direct reliability indicator across both model paths.

Limitations: The latest observation represents a short benchmark period with a limited number of requests. Earlier development runs contained failures before fixes were applied, so longer stable-service testing would be needed for a production objective.

## SLI 5

Indicator: Number of Qwen requests simultaneously running on the GPU through vLLM.

Panel: Concurrent Requests on GPU — Batching Proof (Qwen)

Unit: concurrent requests

Target: Support >= 3 simultaneous Qwen requests without request failure during the tested workload.

Window: Active concurrent benchmark window.

Observed: `vllm:num_requests_running` reached 3 simultaneous requests. Qwen completed 9/9 concurrent requests, achieved 1.24x workload speedup, and reached 89 files/hour.

Evidence: Grafana/Prometheus `vllm:num_requests_running` measurement showing 3 active requests, together with the vLLM runtime evidence and concurrent benchmark results.

Why it fits: Qwen is served using vLLM continuous batching. Concurrent running requests demonstrate that multiple active inference requests can be processed by the serving engine instead of serializing the entire workload.

Limitations: This indicator applies only to Qwen because OpenAI is served through an external API. A three-user test validates the current capstone workload but does not establish the maximum sustainable concurrency of the GPU service.