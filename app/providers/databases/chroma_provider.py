from typing import Any, Dict, List, Optional
from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.interfaces.vector_store import IVectorStore
from app.core.config import settings

class DummyEmbeddingFunction:
    def embed_documents(self, texts):
        return [[0.0] * 1024 for _ in texts]
    def embed_query(self):
        return [0.0] * 1024

class ChromaProvider(IVectorStore):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # We handle embeddings externally, but we need to provide a dummy function
        # to ensure Chroma sets the correct dimension (1024 for GigaChat)
        self._embedding_function = DummyEmbeddingFunction()
        
        import chromadb
        import logging
        logger = logging.getLogger(__name__)
        
        # Get config values with proper fallback to settings
        if config:
            host = config.get("chroma_host") or settings.CHROMA_SERVER_HOST
            port = config.get("chroma_port") or settings.CHROMA_SERVER_PORT
            ssl = config.get("chroma_ssl", settings.CHROMA_SERVER_SSL)
        else:
            host = settings.CHROMA_SERVER_HOST
            port = settings.CHROMA_SERVER_PORT
            ssl = settings.CHROMA_SERVER_SSL
        
        # Handle full URLs in host (extract protocol, host, port, and path)
        path = ""
        if host.startswith("https://"):
            from urllib.parse import urlparse
            parsed = urlparse(host)
            original_host = host
            host = parsed.hostname or host
            if parsed.port:
                port = parsed.port
            ssl = parsed.scheme == "https"
            
            path = parsed.path.rstrip("/") if parsed.path and parsed.path != "/" else ""
            if path:
                logger.info(f"ChromaDB path detected: '{path}'")
                # For paths, we need to use the full URL as the host parameter
                # The chromadb client will handle it correctly
                host = original_host.rstrip("/")
        
        # Disable SSL for internal Docker hostnames (they don't have SSL certificates)
        elif host and not host.startswith("http") and ("localhost" in host or "127.0.0.1" in host or "_" in host or host.endswith(".local")):
            logger.info(f"Detected internal hostname '{host}', disabling SSL")
            ssl = False
        
        logger.info(f"Initializing Chroma provider at {host}:{port} (ssl={ssl})")
        
        # If host contains a full URL with path, pass it directly
        if host.startswith("https://"):
            logger.info(f"Using full ChromaDB URL: {host}")
            self._http_client = chromadb.HttpClient(host=host)
        else:
            # Standard connection without path
            self._http_client = chromadb.HttpClient(
                host=host,
                port=port,
                ssl=ssl
            )
        
        distance_metric = settings.SEARCH_CONFIG.get("distance_metric", "cosine")
        
        logger.info("Connecting to Chroma collection 'chat_history'...")
        self._client = Chroma(
            collection_name="chat_history",
            client=self._http_client,
            embedding_function=self._embedding_function,
            collection_metadata={"hnsw:space": distance_metric}
        )
        logger.info("Chroma provider initialized.")

    async def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]) -> None:
        try:
            texts = [doc["page_content"] for doc in documents]
            metadatas = [doc.get("metadata", {}) for doc in documents]
            ids = [doc.get("id") for doc in documents] # Optional, might be None
            
            # Filter out None ids if necessary, or let Chroma handle it (it generates UUIDs)
            if all(id is None for id in ids):
                ids = None
                
            self._client.add_texts(
                texts=texts,
                metadatas=metadatas,
                embeddings=embeddings,
                ids=ids
            )
        except Exception as e:
            # Log the error appropriately in a real app
            print(f"Error adding documents to Chroma: {e}")
            raise e

    async def similarity_search(
        self, 
        query_embedding: List[float], 
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        try:
            docs_and_scores = self._client.similarity_search_by_vector_with_relevance_scores(
                embedding=query_embedding,
                k=k,
                filter=filter
            )
            
            # Convert Documents back to dicts with scores
            return [
                {
                    "page_content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": score
                }
                for doc, score in docs_and_scores
            ]
        except Exception as e:
            print(f"Error during similarity search in Chroma: {e}")
            raise e

    async def reset(self) -> None:
        """Resets the collection. Useful for testing."""
        try:
            self._client.delete_collection()
            # Re-initialize collection
            self._client = Chroma(
                collection_name="chat_history",
                client=self._http_client,
                embedding_function=self._embedding_function,
                collection_metadata={"hnsw:space": settings.SEARCH_CONFIG.get("distance_metric", "cosine")}
            )
        except Exception as e:
            print(f"Error resetting Chroma collection: {e}")
            raise e

    async def delete_documents(self, ids: List[str]) -> None:
        """Delete documents by IDs."""
        try:
            self._client.delete(ids=ids)
        except Exception as e:
            print(f"Error deleting documents from Chroma: {e}")
            raise e

    async def get_by_filter(self, filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get documents by metadata filter."""
        try:
            # Chroma get returns dict with keys: ids, embeddings, metadatas, documents
            results = self._client.get(where=filter)
            
            documents = []
            if results['ids']:
                for i in range(len(results['ids'])):
                    documents.append({
                        "id": results['ids'][i],
                        "page_content": results['documents'][i] if results['documents'] else "",
                        "metadata": results['metadatas'][i] if results['metadatas'] else {}
                    })
            return documents
        except Exception as e:
            print(f"Error getting documents by filter from Chroma: {e}")
            raise e
