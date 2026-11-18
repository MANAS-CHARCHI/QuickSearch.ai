"""
Build-time script to download and export ML security classifiers & embedding models
to ONNX inside `/opt/models` so Lambda 2 runs offline with fast CPU inference.
"""
import os

MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/opt/models")
SQLI_MODEL_ID = os.getenv("SQLI_MODEL_ID", "cssupport/mobilebert-sql-injection-detect")
PROMPT_INJECTION_MODEL_ID = os.getenv(
    "PROMPT_INJECTION_MODEL_ID", "ProtectAI/deberta-v3-small-prompt-injection-v2"
)
EMBEDDING_MODEL_ID = os.getenv("EMBEDDING_MODEL_ID", "BAAI/bge-small-en-v1.5")


def main() -> None:
    from optimum.onnxruntime import ORTModelForSequenceClassification
    from transformers import AutoTokenizer
    from fastembed import TextEmbedding

    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)

    # 1. SQL Injection Classifier (ONNX)
    sqli_dir = os.path.join(MODEL_CACHE_DIR, "sqli")
    print(f"Exporting SQLi model '{SQLI_MODEL_ID}' to ONNX in '{sqli_dir}'...")
    AutoTokenizer.from_pretrained(SQLI_MODEL_ID).save_pretrained(sqli_dir)
    ORTModelForSequenceClassification.from_pretrained(
        SQLI_MODEL_ID, export=True
    ).save_pretrained(sqli_dir)

    # 2. AI Prompt Injection / Manipulator Classifier (ONNX)
    pi_dir = os.path.join(MODEL_CACHE_DIR, "prompt_injection")
    print(f"Exporting Prompt Injection model '{PROMPT_INJECTION_MODEL_ID}' to ONNX in '{pi_dir}'...")
    AutoTokenizer.from_pretrained(PROMPT_INJECTION_MODEL_ID).save_pretrained(pi_dir)
    ORTModelForSequenceClassification.from_pretrained(
        PROMPT_INJECTION_MODEL_ID, export=True
    ).save_pretrained(pi_dir)

    # 3. FastEmbed 384-dim ONNX Embeddings
    embed_dir = os.path.join(MODEL_CACHE_DIR, "fastembed")
    print(f"Downloading FastEmbed '{EMBEDDING_MODEL_ID}' into '{embed_dir}'...")
    TextEmbedding(model_name=EMBEDDING_MODEL_ID, cache_dir=embed_dir)

    print("All Lambda 2 ONNX models baked successfully.")


if __name__ == "__main__":
    main()
