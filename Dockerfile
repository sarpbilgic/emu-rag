FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

RUN python -c "\
from fastembed import TextEmbedding; \
TextEmbedding(model_name='intfloat/multilingual-e5-large', cache_dir='./model_cache'); \
"

COPY . .

EXPOSE 7860

CMD sh -c "python -m src.chunkers.ingestion && uvicorn src.api.main:app --host 0.0.0.0 --port 7860"