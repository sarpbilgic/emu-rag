from typing import Optional
import logging

logger = logging.getLogger(__name__)

# fastembed changed import paths across versions
try:
    from fastembed.rerank.cross_encoder import TextCrossEncoder
except ImportError:
    from fastembed import TextCrossEncoder


class RerankerClient:
    DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"
    
    def __init__(self, model_name: Optional[str] = None, cache_dir: str = "./model_cache"):
        self.model_name = model_name or self.DEFAULT_MODEL
        logger.info(f"Loading reranker: {self.model_name}")
        
        self.model = TextCrossEncoder(model_name=self.model_name, cache_dir=cache_dir)
        logger.info("Reranker ready")
    
    def rerank(self, query: str, documents: list[str]):
        return self.model.rerank(query, documents)
