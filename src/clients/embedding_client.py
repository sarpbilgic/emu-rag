from llama_index.embeddings.voyageai import VoyageEmbedding
from llama_index.core import Settings as LlamaSettings
from src.core.settings import settings
import time

class EmbeddingClient:
    def __init__(self):
        self.embed_model = VoyageEmbedding(
            voyage_api_key=settings.voyage_api_key, 
            model_name="voyage-3.5",          
            truncation=True,
            embed_batch_size=5                
        )
        LlamaSettings.embed_model = self.embed_model

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return self.embed_model.get_text_embedding_batch(documents)

    def embed_query(self, query: str) -> list[float]:
        return self.embed_model.get_query_embedding(query)

    def get_embed_model(self) -> VoyageEmbedding:
        return self.embed_model

embedding_client = EmbeddingClient()