from qdrant_client import QdrantClient
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import StorageContext
from src.core.settings import settings # Senin gönderdiğin Pydantic ayarları

class QdrantClientManager:
    def __init__(self, collection_name: str = "emu_regulations"):
        self.client = QdrantClient(
            url=settings.qdrant_url, 
            api_key=settings.qdrant_api_key
        )
        self.collection_name = collection_name

    def get_vector_store(self) -> QdrantVectorStore:
        return QdrantVectorStore(
            client=self.client, 
            collection_name=self.collection_name
        )

    def get_storage_context(self) -> StorageContext:
        vector_store = self.get_vector_store()
        return StorageContext.from_defaults(vector_store=vector_store)
    