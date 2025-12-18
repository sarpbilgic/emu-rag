from qdrant_client import QdrantClient
from core.settings import Settings

class QdrantClient:
    def __init__(self):
        self.client = QdrantClient(
            url=Settings.QDRANT_URL,
            api_key=Settings.QDRANT_API_KEY,
        )

    