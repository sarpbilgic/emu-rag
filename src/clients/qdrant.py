from qdrant_client import QdrantClient
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import Document
from qdrant_client.http.models import Distance
from src.core.settings import settings

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
            collection_name=self.collection_name,
            distance=Distance.COSINE,
            dimensions=3072
        )

    def get_storage_context(self) -> StorageContext:
        vector_store = self.get_vector_store()
        return StorageContext.from_defaults(vector_store=vector_store)

    def get_query_engine(self, documents=None):
        manager = QdrantClientManager()
        storage_context = manager.get_storage_context()
        
        if documents:
            index = VectorStoreIndex.from_documents(
                documents, 
                storage_context=storage_context
            )
        else:
            index = VectorStoreIndex.from_vector_store(
                manager.get_vector_store()
            )
        
        return index.as_query_engine()