"""
Build-time script to bake SmolVLM-500M-Instruct weights into the Lambda 3 container image
so the AWS Firecracker microVM / local SAM container executes 100% offline with zero
model download latency during invocations.
"""
import os
from huggingface_hub import snapshot_download

MODEL_ID = os.getenv("VLM_MODEL_ID", "HuggingFaceTB/SmolVLM-500M-Instruct")
MODEL_DIR = os.getenv("VLM_MODEL_DIR", "/opt/models/vlm")


def main() -> None:
    os.makedirs(MODEL_DIR, exist_ok=True)
    print(f"Downloading VLM model '{MODEL_ID}' into '{MODEL_DIR}'...")
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=MODEL_DIR,
        local_dir_use_symlinks=False,
    )
    print("VLM model successfully baked into container image.")


if __name__ == "__main__":
    main()
