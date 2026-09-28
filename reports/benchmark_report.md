# Final Benchmark Report
## 1. Project Overview and Business Problem

This project focuses on evaluating AI models for automated analysis and tagging of learning content.

The core business challenge is to identify a model that can reliably analyze educational materials, extract relevant topics and concepts, and classify content difficulty using a consistent structured output.

To support an informed model selection, candidate models are evaluated on the same dataset and compared against a human-reviewed annotation key. The assessment considers both task performance and deployment-related factors, including latency, resource requirements, scalability, and serving efficiency.

The overall objective is to recommend a content-tagging solution that provides strong output quality while remaining efficient, scalable, and practical for real-world deployment.


## 2. Use Case and Scope

This project addresses the automated analysis of learning content for structured content tagging and difficulty classification.

The system is designed to process each learning item and produce a consistent structured output that includes the key topics and concepts identified in the content, the assigned difficulty level, and supporting metadata such as confidence and notes.

The project scope is centered on evaluating two candidate models, OpenAI and Qwen, using the same evaluation dataset and a common output schema. Their results are compared against a human-reviewed annotation key to assess the quality and reliability of the generated tags and difficulty classifications.

In addition to task quality, the evaluation also considers practical deployment factors such as latency, resource requirements, inference efficiency, and ease of serving.

The evaluation is based on the actual content of each file. File names are not treated as ground truth or used as a substitute for content analysis.

## 3. Models Tested

The benchmark evaluated two models representing distinct deployment strategies: a commercial API-based model and an open-weight model deployed within the project infrastructure.

### GPT-4o-mini
GPT-4o-mini was used as the commercial reference model to establish a quality baseline for content tagging and difficulty classification. It was evaluated using the same dataset, prompt structure, and output schema applied across the benchmark.

### Qwen/Qwen2.5-VL-3B-Instruct-AWQ
Qwen/Qwen2.5-VL-3B-Instruct-AWQ was selected as the open-weight deployment candidate. The AWQ-quantized variant was evaluated to assess whether a locally deployable model could deliver competitive task performance while providing greater control over infrastructure, serving configuration, and operational cost.

Both models were evaluated under a consistent methodology to support a fair comparison across task quality and operational characteristics. Detailed benchmark results and deployment trade-offs are presented in the following sections.

## 4. Deployment Architecture

The deployment architecture was designed to support reliable and reproducible serving of the open-weight model within the project infrastructure.

The Qwen/Qwen2.5-VL-3B-Instruct-AWQ model was containerized using Docker and deployed on Kubernetes. The inference service was exposed through an API endpoint, allowing the evaluation pipeline and demo application to submit content for analysis and receive structured model outputs.

The deployment stack includes:
- Docker for packaging the model and application dependencies.
- Kubernetes for container orchestration and service management.
- vLLM as the inference engine for serving the Qwen model.
- An API layer for submitting requests and returning structured responses.
- Monitoring components for tracking service health, latency, throughput, GPU utilization, and memory usage.

GPT-4o-mini was accessed through its external API and was used as the commercial reference model within the same evaluation workflow.

This architecture enabled a consistent benchmark process while also allowing the open-weight model to be evaluated under realistic deployment conditions.

## 5. Evaluation Dataset and Annotation Process

## 6. Evaluation Methodology

## 7. Benchmark Results

## 8. Accuracy / Task Performance Analysis

## 9. Latency and Token/Cost Analysis

## 10. Deployment and Operational Trade-offs

## 11. Production Handoff / AI Hub Demonstration

## 12. Lessons Learned

## 13. Optional Stretch Work
