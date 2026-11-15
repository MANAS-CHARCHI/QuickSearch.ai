import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings


class ChromaService:
    def __init__(self):
        # Initialize client (local persistent or HTTP depending on environment)
        try:
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                settings=ChromaSettings(allow_reset=True, anonymized_telemetry=False),
            )
        except Exception:
            # Fallback to local persistent directory for standalone dev
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIRECTORY,
                settings=ChromaSettings(allow_reset=True, anonymized_telemetry=False),
            )

    def get_or_create_collection(self, name: str = "document_vault"):
        return self.client.get_or_create_collection(name=name)

    def ping(self) -> bool:
        try:
            return self.client.heartbeat() > 0
        except Exception:
            return False


chroma_service = ChromaService()
