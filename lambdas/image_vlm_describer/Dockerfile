FROM public.ecr.aws/lambda/python:3.12

# Install CPU-only PyTorch wheels to keep the Lambda microVM image lean
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY download_vlm.py vlm_engine.py app.py ${LAMBDA_TASK_ROOT}/

# Optional build-time model baking: pass --build-arg BAKE_VLM_MODEL=true for offline AWS Firecracker deploys
ARG BAKE_VLM_MODEL=false
ENV VLM_MODEL_ID=HuggingFaceTB/SmolVLM-500M-Instruct \
    VLM_MODEL_DIR=/opt/models/vlm \
    HF_HOME=/tmp/hf_cache

RUN if [ "$BAKE_VLM_MODEL" = "true" ]; then python3 ${LAMBDA_TASK_ROOT}/download_vlm.py; fi

CMD ["app.lambda_handler"]
