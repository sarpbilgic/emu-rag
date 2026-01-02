from qdrant_client import AsyncQdrantClient
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import Document
from typing import Optional, List
from src.core.settings import settings
import logging

class QdrantClientManager:
    def __init__(self, collection_name: str = "emu_regulations"):
        self.client = AsyncQdrantClient(
            url=settings.qdrant_url, 
            api_key=settings.qdrant_api_key
        )
        self.collection_name = collection_name

    async def clear_collection(self) -> bool:
        try:
            collections = (await self.client.get_collections()).collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if exists:
                await self.client.delete_collection(self.collection_name)
                logging.info(f"[OK] Deleted collection: {self.collection_name}")
            else:
                logging.info(f"Collection '{self.collection_name}' does not exist yet")
            
            return True
        except Exception as e:
            logging.error(f"[ERROR] Failed to clear collection: {e}")
            return False

    def get_vector_store(self) -> QdrantVectorStore:
        return QdrantVectorStore(
            aclient=self.client, 
            collection_name=self.collection_name,
            enable_hybrid = False
        )

    def get_storage_context(self) -> StorageContext:
        vector_store = self.get_vector_store()
        return StorageContext.from_defaults(vector_store=vector_store)

    def get_query_engine(self, documents: Optional[List[Document]] = None):
        storage_context = self.get_storage_context()
        
        if documents:
            index = VectorStoreIndex.from_documents(
                documents, 
                storage_context=storage_context
            )
        else:
            index = VectorStoreIndex.from_vector_store(
                self.get_vector_store()
            )
        
        return index.as_query_engine()

    def get_retriever(self, top_k: int = 5):
        storage_context = self.get_storage_context()
        index = VectorStoreIndex.from_vector_store(
            self.get_vector_store(),
            storage_context=storage_context
        )
        return index.as_retriever(
            similarity_top_k=top_k,
            vector_store_query_mode="hybrid",
        )
   