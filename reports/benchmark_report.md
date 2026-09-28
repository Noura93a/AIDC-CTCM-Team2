# Final Benchmark Report

## 1. Project Overview and Business Problem

This project evaluates AI-based approaches for the automated analysis of learning content, with a focus on content tagging, difficulty classification, and skills mapping.

The business challenge is to identify a solution that can reliably interpret educational materials, extract the most relevant topics and concepts, determine the appropriate level of difficulty, and map the content to an established skills taxonomy.

To support an evidence-based model selection, the project applies a consistent benchmarking framework that evaluates both task quality and operational performance. Key considerations include tagging accuracy, skills-mapping quality, structured-output reliability, latency, resource requirements, scalability, and inference cost.

The overall objective is to recommend a solution that combines reliable content understanding with efficient, scalable, and practical deployment characteristics.

## 2. Use Case and Scope


The use case focuses on applying AI to analyze learning content and generate structured outputs that support content tagging, difficulty classification, and skills mapping.

For each learning item, the system is expected to identify the most relevant topics and concepts, assign a difficulty level of Beginner, Intermediate, or Advanced, and map the content to relevant skills from the provided taxonomy. The system also returns supporting information, including a concise content summary, confidence score, and learning-objective notes.

The project scope includes the evaluation of GPT-4o-mini and Qwen/Qwen2.5-VL-3B-Instruct-AWQ using the same evaluation dataset, prompt structure, and output requirements. Model outputs are compared against a human-reviewed reference set to assess both task quality and operational performance.

The evaluation is based on the actual content of each file rather than file names, ensuring that model predictions reflect the learning material itself.

## 3. Models Tested


The benchmark evaluated two models representing distinct deployment approaches: a commercial API-based model and an open-weight model deployed within the project infrastructure.

### GPT-4o-mini
GPT-4o-mini was used as the commercial reference model to establish a strong quality baseline for content tagging, difficulty classification, and skills mapping. It was evaluated using the same dataset, prompt structure, and structured-output requirements applied throughout the benchmark.

### Qwen/Qwen2.5-VL-3B-Instruct-AWQ
Qwen/Qwen2.5-VL-3B-Instruct-AWQ was selected as the open-weight deployment candidate. The AWQ-quantized variant was evaluated to determine whether a locally deployable model could provide competitive task performance while offering greater control over infrastructure, serving configuration, and operational cost.

Both models were evaluated under a consistent methodology to support a fair comparison across task quality and operational characteristics. Detailed performance results and deployment trade-offs are presented in later sections of this report.

## 4. Deployment Architecture

The deployment architecture was designed to support reliable, reproducible, and GPU-enabled inference for the open-weight model within the project infrastructure.

The application is containerized using Docker and built on an NVIDIA CUDA 12.4.1 runtime image. The container includes the Python runtime, model dependencies, content-processing utilities, and required project data resources. The application is served through Uvicorn on port 8000, with a container-level health check configured against the `/health` endpoint.

The application is deployed on Kubernetes in the `ctcm` namespace using a single-replica deployment. The pod requests one NVIDIA GPU, 2 CPU cores, and 8 GiB of memory, with limits of 4 CPU cores and 16 GiB of memory. A persistent volume is used for the Hugging Face model cache, while Kubernetes readiness and liveness probes monitor the service through the `/health` endpoint.

The service is exposed through a Kubernetes NodePort service on port 8000, using node port 30801 for external access to the application.

The deployment also integrates the project skills taxonomy and reviewed golden dataset as application resources, while sensitive credentials such as the OpenAI API key are managed through Kubernetes Secrets.

A shared prompting framework is used across the evaluated models to maintain consistency in model behavior and output structure. The system prompt requires structured JSON responses containing a content summary, predicted tags, difficulty level, predicted skills, confidence score, and learning-objective notes.

This architecture supports a consistent evaluation workflow while enabling Qwen/Qwen2.5-VL-3B-Instruct-AWQ to be assessed under realistic deployment conditions within the project infrastructure.

## 5. Evaluation Dataset and Annotation Process

The evaluation dataset comprises 12 learning-content items selected to assess model performance across content tagging, difficulty classification, and skills mapping.

Each item is paired with a human-reviewed reference record that defines the expected content type, reference tags, difficulty level, mapped skills, and supporting notes. These reviewed annotations serve as the benchmark ground truth for evaluating the outputs generated by each model.

The annotation process was designed to capture specific concepts, techniques, and skills represented in the learning material rather than relying on broad subject-level labels. Difficulty classifications were standardized across three levels: Beginner, Intermediate, and Advanced.

To ensure a controlled and comparable evaluation, both GPT-4o-mini and Qwen/Qwen2.5-VL-3B-Instruct-AWQ were assessed against the same reviewed reference set.

Model performance was evaluated based on the actual content of each file. File names were not treated as ground truth and were not used as a substitute for content-level analysis.

## 6. Evaluation Methodology

Model performance was evaluated using a predefined scoring framework that compares each model output against the reviewed golden reference.

For difficulty classification, the predicted label was compared directly with the reference label. Tagging performance was assessed using overlap-based and semantic measures, including tag precision, tag recall, and semantic F1. Skills mapping was evaluated by comparing the predicted skills with the reference skills using overlap, precision, and recall measures.

Structured-output validity was also measured to verify that each model consistently returned the required response format.

In addition to task-quality metrics, the benchmark captured operational measures such as end-to-end latency, token usage, generation speed, estimated inference cost, and estimated processing throughput.

Results were calculated at the individual-file level and then aggregated by model to produce the final benchmark summary used for model comparison.

## 7. Benchmark Results

## 7. Benchmark Results

The final benchmark compared GPT-4o-mini and Qwen/Qwen2.5-VL-3B-Instruct-AWQ across model-quality and operational metrics.

| Metric | Qwen/Qwen2.5-VL-3B-Instruct-AWQ | GPT-4o-mini |
|---|---:|---:|
| Evaluation Items | 12 | 12 |
| Tagging / Classification Accuracy | 41.8% | 50.1% |
| Difficulty Accuracy | 66.7% | 83.3% |
| Tag Semantic F1 | 43.4% | 53.4% |
| Tag Precision | 31.9% | 29.1% |
| Tag Recall | 23.7% | 24.4% |
| Skills-Mapping Accuracy | 27.0% | 24.5% |
| Skill Precision | 35.4% | 33.3% |
| Skill Recall | 47.2% | 44.4% |
| Retrieval Quality | 86.1% pool recall | 86.1% pool recall |
| Structured-Output Validity | 100% | 100% |
| Average Latency | 56.39 s | 71.98 s |
| Average Generation Speed | 29.16 tokens/s | 105.67 tokens/s |
| Estimated Processing Throughput | 63.8 items/hour | 50.0 items/hour |
| Estimated Cost per 1,000 Files | $4.79 | $6.22 |

The benchmark results highlight distinct strengths across the two models. GPT-4o-mini achieved higher tagging/classification accuracy, difficulty accuracy, and tag semantic F1. In contrast, Qwen achieved stronger skills-mapping metrics, lower average end-to-end latency, higher estimated processing throughput, and a lower estimated cost per 1,000 files.

Both models achieved 100% structured-output validity, demonstrating consistent compliance with the required response schema.

## 8. Accuracy / Task Performance Analysis

The quality results indicate that GPT-4o-mini performed better on the core content-understanding tasks, particularly tagging/classification accuracy, difficulty classification, and tag semantic similarity.

GPT-4o-mini achieved 50.1% tagging/classification accuracy compared with 41.8% for Qwen, while difficulty-classification accuracy reached 83.3% compared with 66.7%. It also achieved a higher tag semantic F1 score of 53.4%, indicating stronger alignment with the human-reviewed reference tags.

Qwen, however, showed stronger performance on skills mapping. It achieved 27.0% skills-mapping accuracy compared with 24.5% for GPT-4o-mini, together with higher skill precision and recall.

Both models achieved 100% structured-output validity, demonstrating reliable compliance with the required output schema.

Overall, GPT-4o-mini demonstrated stronger performance on content tagging and difficulty classification, while Qwen showed a relative advantage in skills mapping. These results suggest that model selection should consider the priority of the target task rather than relying on a single overall metric.

## 9. Latency and Token/Cost Analysis

The benchmark results showed distinct operational characteristics between GPT-4o-mini and Qwen/Qwen2.5-VL-3B-Instruct-AWQ.

Qwen achieved a lower average end-to-end latency of 56.39 seconds per item, compared with 71.98 seconds for GPT-4o-mini. This resulted in a higher estimated processing throughput of 63.8 items per hour for Qwen, compared with 50.0 items per hour for GPT-4o-mini.

GPT-4o-mini achieved a higher average generation speed of 105.67 tokens per second, compared with 29.16 tokens per second for Qwen. This indicates that token-generation speed and overall end-to-end processing latency represent different aspects of system performance.

Token usage also differed substantially between the two models. Across the 12 evaluation items, Qwen processed a total of 107,195 tokens, while GPT-4o-mini recorded 287,621 total tokens. This difference is relevant when considering inference efficiency and cost alongside model quality.

The estimated processing cost was lower for Qwen, at $4.79 per 1,000 files, compared with $6.22 per 1,000 files for GPT-4o-mini.

Grafana monitoring was used to observe the operational behavior of the Qwen deployment during the load test. During the captured test window, the deployment reached up to three concurrent GPU requests. The dashboard was used to monitor Time to First Token (TTFT), Time per Output Token (TPOT), queue time, request activity, generation throughput, GPU-related behavior, and application errors.

The observed monitoring data showed variation in TTFT and queue time during the test window, highlighting the importance of evaluating inference performance under concurrent workloads in addition to average benchmark latency.

Overall, Qwen demonstrated lower average end-to-end latency, higher estimated processing throughput, lower total token usage, and lower estimated cost, while GPT-4o-mini achieved significantly higher token-generation speed. The combined benchmark and monitoring results provide a broader view of both model-level performance and deployed inference behavior.

## 10. Deployment and Operational Trade-offs

## 11. Production Handoff / AI Hub Demonstration

## 12. Lessons Learned

## 13. Optional Stretch Work

