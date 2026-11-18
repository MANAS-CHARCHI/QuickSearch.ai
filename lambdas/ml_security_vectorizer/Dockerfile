FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY download_models.py chunker.py pgvector_store.py app.py ${LAMBDA_TASK_ROOT}/
COPY scanners ${LAMBDA_TASK_ROOT}/scanners

ARG BAKE_MODELS=false
ENV MODEL_CACHE_DIR=/opt/models \
    HF_HOME=/tmp/hf_cache \
    FASTEMBED_CACHE_PATH=/tmp/fastembed_cache

RUN if [ "$BAKE_MODELS" = "true" ]; then python3 ${LAMBDA_TASK_ROOT}/download_models.py; fi

CMD ["app.lambda_handler"]
