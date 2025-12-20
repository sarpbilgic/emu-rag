from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.core import Settings as LlamaSettings
from src.core.settings import settings
import time
import logging

class EmbeddingClient:
    def __init__(self):
        logging.info("Initializing FastEmbed embeddings...")
        self.embed_model = FastEmbedEmbedding(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            cache_folder="./model_cache",
            )
        LlamaSettings.embed_model = self.embed_model
        logging.info("Embedding model loaded successfully")


    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return self.embed_model.get_text_embedding_batch(documents)

    def embed_query(self, query: str) -> list[float]:
        return self.embed_model.get_query_embedding(query)

    def get_embed_model(self) -> FastEmbedEmbedding:
        return self.embed_model

embedding_client = EmbeddingClient()