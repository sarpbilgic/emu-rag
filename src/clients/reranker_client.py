from fastembed.rerank.cross_encoder import TextCrossEncoder
from typing import Optional
import logging
from src.core.settings import settings
logger = logging.getLogger(__name__)


class RerankerClient:
    def __init__(self, cache_dir: str = "./model_cache"):
        self.model_name = settings.reranker_model
        logger.info(f"Loading reranker: {self.model_name}")
        
        self.model = TextCrossEncoder(model_name=self.model_name, cache_dir=cache_dir)
        logger.info("Reranker ready")
    
    def rerank(self, query: str, documents: list[str]):
        return list(self.model.rerank(query, documents))
