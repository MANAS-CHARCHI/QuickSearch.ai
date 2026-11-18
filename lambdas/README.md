# Vault City AWS SAM Local Lambda Pipeline

Local & cloud AWS SAM setup for the 3-stage document security, VLM visual understanding, and PostgreSQL `pgvector` RAG ingestion pipeline.

## Lambda Functions

| Function | Endpoint (`sam local start-api`) | Responsibility |
| :--- | :--- | :--- |
| **`FileScanAndExtractFunction`** | `POST /scan-extract` | Scans files with ClamAV (`clamav:3310 INSTREAM`), extracts text (`PDF`, `DOCX`, `TXT`), and routes images / scanned PDFs to Lambda 3 |
| **`ImageVLMDescriptionFunction`** | `POST /describe-image` | **Isolated VLM MicroVM** (zero DB/Redis/secret access) — runs `SmolVLM-500M-Instruct` (or local Ollama Metal) to describe images & transcribe visible text |
| **`TextSecurityAndVectorizeFunction`** | `POST /security-vectorize` | Dual ONNX ML scanners (`SQL Injection` + `AI Prompt Injection / Manipulator`) → recursive chunking → FastEmbed (`384-dim`) → atomic upsert into PostgreSQL `document_chunks` (`pgvector`) |

## Prerequisites (macOS)

```bash
brew install aws-sam-cli
sam --version
```

## Quickstart

```bash
# 1. Start backing services (Postgres+pgvector, Redis, ClamAV, MinIO)
cd lambdas
make up

# 2. Validate & build all 3 Lambda container images
make validate
make build

# 3. Test individual Lambdas with sample events
make test-clean
make test-virus
make test-vlm
make test-sqli
make test-prompt-injection

# 4. Run local API Gateway (port 3001) & Lambda Invoke endpoint (port 3002)
make start-api
# In a second terminal (needed for Lambda 1 -> Lambda 3 / Lambda 2 chaining):
make start-lambda
```

## Fast Local VLM Mode (Apple Silicon Metal via Ollama)
To run Lambda 3 in <1s locally using your Mac's GPU via Ollama:
1. Run `ollama pull moondream` (or `qwen2.5vl:3b`).
2. Set `"VLM_MODE": "ollama"` inside `lambdas/env.json` under `ImageVLMDescriptionFunction`.
3. For standalone AWS Firecracker microVM production deploys, build with `--build-arg BAKE_VLM_MODEL=true` and `VLM_MODE=embedded`.
