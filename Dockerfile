FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

RUN python -c "\
from fastembed import TextEmbedding, SparseTextEmbedding; \
TextEmbedding(model_name='intfloat/multilingual-e5-large', cache_dir='./model_cache'); \
SparseTextEmbedding(model_name='prithivida/Splade_PP_en_v1', cache_dir='./model_cache'); \
"

RUN python -c "\
try: from fastembed.rerank.cross_encoder import TextCrossEncoder; \
except ImportError: from fastembed import TextCrossEncoder; \
TextCrossEncoder(model_name='BAAI/bge-reranker-v2-m3', cache_dir='./model_cache'); \
"

COPY . .

EXPOSE 7860

CMD sh -c "uvicorn src.api.main:app --host 0.0.0.0 --port 7860 --proxy-headers --forwarded-allow-ips='*'"