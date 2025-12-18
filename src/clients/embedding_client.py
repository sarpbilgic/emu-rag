from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core import Settings as LlamaSettings
from src.core.settings import settings


class EmbeddingClient:
    def __init__(self):
        self.embed_model = GeminiEmbedding(
            api_key=settings.gemini_api_key,
            model_name="models/text-embedding-004",
        )
        LlamaSettings.embed_model = self.embed_model

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        return self.embed_model.get_text_embedding_batch(documents)

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query."""
        return self.embed_model.get_query_embedding(query)

    def get_embed_model(self) -> GeminiEmbedding:
        return self.embed_model


embedding_client = EmbeddingClient()
