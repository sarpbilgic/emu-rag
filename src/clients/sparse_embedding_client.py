from fastembed import SparseTextEmbedding
from typing import List, Tuple
import logging

class SparseEmbeddingClient:  
    def __init__(self, model_name: str = "prithivida/Splade_PP_en_v1"):
        logging.info(f"Initializing SPLADE sparse embeddings ({model_name})...")
        self.model = SparseTextEmbedding(
            model_name=model_name,
            cache_dir="./model_cache",
        )
        logging.info("Sparse embedding model loaded successfully")
    
    def embed_documents(self, documents: List[str]) -> Tuple[List[List[int]], List[List[float]]]:
        embeddings = list(self.model.embed(documents))
        all_indices = [emb.indices.tolist() for emb in embeddings]
        all_values = [emb.values.tolist() for emb in embeddings]
        return (all_indices, all_values)
    
    def embed_query(self, query: str) -> Tuple[List[int], List[float]]:
        embedding = list(self.model.query_embed(query))[0]
        return (embedding.indices.tolist(), embedding.values.tolist())