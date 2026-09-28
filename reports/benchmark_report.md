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

The application is containerized using Docker and built on an NVIDIA CUDA 12.4.1 runtime image. The container includes the Python runtime, model dependencies, content-processing utilities, and required project data resources. The application is served through Uvicorn on port 8000, with a container-level health check configured against the `/health` endpoint. :chatgpt-content-reference{index="0"}

The application is deployed on Kubernetes in the `ctcm` namespace using a single-replica deployment. The pod requests one NVIDIA GPU, 2 CPU cores, and 8 GiB of memory, with limits of 4 CPU cores and 16 GiB of memory. A persistent volume is used for the Hugging Face model cache, while Kubernetes readiness and liveness probes monitor the service through the `/health` endpoint. :chatgpt-content-reference{index="1"}

The service is exposed through a Kubernetes NodePort service on port 8000, using node port 30801 for external access to the application. :chatgpt-content-reference{index="2"}

The deployment also integrates the project skills taxonomy and reviewed golden dataset as application resources, while sensitive credentials such as the OpenAI API key are managed through Kubernetes Secrets. :chatgpt-content-reference{index="3"}

A shared prompting framework is used across the evaluated models to maintain consistency in model behavior and output structure. The system prompt requires structured JSON responses containing a content summary, predicted tags, difficulty level, predicted skills, confidence score, and learning-objective notes. :chatgpt-content-reference{index="4"}

This architecture supports a consistent evaluation workflow while enabling Qwen/Qwen2.5-VL-3B-Instruct-AWQ to be assessed under realistic deployment conditions within the project infrastructure.

## 5. Evaluation Dataset and Annotation Process

## 6. Evaluation Methodology

## 7. Benchmark Results

## 8. Accuracy / Task Performance Analysis

## 9. Latency and Token/Cost Analysis

## 10. Deployment and Operational Trade-offs

## 11. Production Handoff / AI Hub Demonstration

## 12. Lessons Learned

## 13. Optional Stretch Work
