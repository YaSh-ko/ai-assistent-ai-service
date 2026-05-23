"""
Milvus Vector Store Provider

Implements IVectorStore interface using Milvus as the backend.
Milvus is a high-performance vector database designed for similarity search.
"""

import logging
from typing import Any, Dict, List, Optional
from app.interfaces.vector_store import IVectorStore
from app.core.config import settings

logger = logging.getLogger(__name__)


class MilvusProvider(IVectorStore):
    """
    Milvus implementation of IVectorStore.
    
    Provides vector storage and similarity search using Milvus.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Milvus provider.
        
        Args:
            config: Configuration dict with:
                - milvus_host: Milvus server host (default: localhost)
                - milvus_port: Milvus server port (default: 19530)
                - milvus_user: Username for authentication (optional)
                - milvus_password: Password for authentication (optional)
                - milvus_collection: Collection name (default: chat_history)
                - embedding_dimension: Vector dimension (default: 1024)
        """
        try:
            from pymilvus import (
                connections,
                Collection,
                CollectionSchema,
                FieldSchema,
                DataType,
                utility
            )
            self._pymilvus = {
                'connections': connections,
                'Collection': Collection,
                'CollectionSchema': CollectionSchema,
                'FieldSchema': FieldSchema,
                'DataType': DataType,
                'utility': utility
            }
        except ImportError:
            raise ImportError(
                "pymilvus is not installed. Install it with: pip install pymilvus"
            )
        
        # Configuration
        self._config = config or {}
        self._host = self._config.get("milvus_host", settings.MILVUS_HOST if hasattr(settings, 'MILVUS_HOST') else "localhost")
        self._port = self._config.get("milvus_port", settings.MILVUS_PORT if hasattr(settings, 'MILVUS_PORT') else 19530)
        self._user = self._config.get("milvus_user", settings.MILVUS_USER if hasattr(settings, 'MILVUS_USER') else "")
        self._password = self._config.get("milvus_password", settings.MILVUS_PASSWORD if hasattr(settings, 'MILVUS_PASSWORD') else "")
        self._collection_name = self._config.get("milvus_collection", "chat_history")
        self._embedding_dim = self._config.get("embedding_dimension", settings.EMBEDDING_CONFIG.get("dimension", 1024))
        
        # Distance metric
        distance_metric = settings.SEARCH_CONFIG.get("distance_metric", "cosine")
        # Map to Milvus metric types
        metric_map = {
            "cosine": "COSINE",
            "l2": "L2",
            "ip": "IP"  # Inner Product
        }
        self._metric_type = metric_map.get(distance_metric.lower(), "COSINE")
        
        logger.info(f"Initializing Milvus provider at {self._host}:{self._port}")
        
        # Connect to Milvus
        self._connect()
        
        # Initialize collection
        self._init_collection()
        
        logger.info(f"Milvus provider initialized with collection '{self._collection_name}'")
    
    def _connect(self):
        """Establish connection to Milvus server."""
        connections = self._pymilvus['connections']
        
        try:
            # Check if already connected
            if connections.has_connection("default"):
                connections.disconnect("default")
            
            # Connect with or without authentication
            if self._user and self._password:
                connections.connect(
                    alias="default",
                    host=self._host,
                    port=self._port,
                    user=self._user,
                    password=self._password
                )
            else:
                connections.connect(
                    alias="default",
                    host=self._host,
                    port=self._port
                )
            
            logger.info("Successfully connected to Milvus")
            
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def _init_collection(self):
        """Initialize or load the collection."""
        Collection = self._pymilvus['Collection']
        CollectionSchema = self._pymilvus['CollectionSchema']
        FieldSchema = self._pymilvus['FieldSchema']
        DataType = self._pymilvus['DataType']
        utility = self._pymilvus['utility']
        
        # Check if collection exists
        if utility.has_collection(self._collection_name):
            logger.info(f"Loading existing collection '{self._collection_name}'")
            self._collection = Collection(self._collection_name)
            self._collection.load()
        else:
            logger.info(f"Creating new collection '{self._collection_name}'")
            
            # Define schema
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self._embedding_dim),
                FieldSchema(name="page_content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="metadata", dtype=DataType.JSON)
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Chat history with embeddings"
            )
            
            # Create collection
            self._collection = Collection(
                name=self._collection_name,
                schema=schema
            )
            
            # Create index for vector field
            index_params = {
                "metric_type": self._metric_type,
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            
            self._collection.create_index(
                field_name="embedding",
                index_params=index_params
            )
            
            # Load collection into memory
            self._collection.load()
            
            logger.info(f"Collection '{self._collection_name}' created and loaded")
    
    async def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]) -> None:
        """
        Add documents and their embeddings to Milvus.
        
        Args:
            documents: List of document dicts with 'id', 'page_content', 'metadata'
            embeddings: List of embedding vectors
        """
        try:
            if not documents or not embeddings:
                logger.warning("No documents or embeddings to add")
                return
            
            if len(documents) != len(embeddings):
                raise ValueError(f"Documents count ({len(documents)}) != embeddings count ({len(embeddings)})")
            
            # Prepare data
            ids = []
            contents = []
            metadatas = []
            
            for i, doc in enumerate(documents):
                # Generate ID if not provided
                doc_id = doc.get("id")
                if not doc_id:
                    import uuid
                    doc_id = str(uuid.uuid4())
                
                ids.append(doc_id)
                contents.append(doc.get("page_content", ""))
                metadatas.append(doc.get("metadata", {}))
            
            # Insert data
            data = [
                ids,
                embeddings,
                contents,
                metadatas
            ]
            
            self._collection.insert(data)
            self._collection.flush()
            
            logger.info(f"Added {len(documents)} documents to Milvus")
            
        except Exception as e:
            logger.error(f"Error adding documents to Milvus: {e}")
            raise
    
    async def similarity_search(
        self, 
        query_embedding: List[float], 
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            query_embedding: Query vector
            k: Number of results to return
            filter: Metadata filter (optional)
            
        Returns:
            List of documents with similarity scores
        """
        try:
            # Prepare search parameters
            search_params = {
                "metric_type": self._metric_type,
                "params": {"nprobe": 10}
            }
            
            # Build filter expression if provided
            expr = None
            if filter:
                # Convert filter dict to Milvus expression
                # Example: {"user_id": "123"} -> "metadata['user_id'] == '123'"
                conditions = []
                for key, value in filter.items():
                    if isinstance(value, bool):
                        conditions.append(f"metadata['{key}'] == {str(value).lower()}")
                    elif isinstance(value, str):
                        conditions.append(f"metadata['{key}'] == '{value}'")
                    elif isinstance(value, (int, float)):
                        conditions.append(f"metadata['{key}'] == {value}")
                
                if conditions:
                    expr = " and ".join(conditions)
            
            # Perform search
            results = self._collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=k,
                expr=expr,
                output_fields=["id", "page_content", "metadata"]
            )
            
            # Format results
            documents = []
            for hits in results:
                for hit in hits:
                    documents.append({
                        "id": hit.entity.get("id"),
                        "page_content": hit.entity.get("page_content"),
                        "metadata": hit.entity.get("metadata", {}),
                        "score": float(hit.score)
                    })
            
            logger.info(f"Found {len(documents)} similar documents")
            return documents
            
        except Exception as e:
            logger.error(f"Error during similarity search in Milvus: {e}")
            raise
    
    async def reset(self) -> None:
        """
        Reset the collection by dropping and recreating it.
        Useful for testing.
        """
        try:
            utility = self._pymilvus['utility']
            
            # Drop collection if exists
            if utility.has_collection(self._collection_name):
                self._collection.drop()
                logger.info(f"Dropped collection '{self._collection_name}'")
            
            # Recreate collection
            self._init_collection()
            logger.info(f"Reset collection '{self._collection_name}'")
            
        except Exception as e:
            logger.error(f"Error resetting Milvus collection: {e}")
            raise
    
    async def delete_documents(self, ids: List[str]) -> None:
        """
        Delete documents by IDs.
        
        Args:
            ids: List of document IDs to delete
        """
        try:
            if not ids:
                logger.warning("No IDs provided for deletion")
                return
            
            # Build expression for deletion
            id_list = "', '".join(ids)
            expr = f"id in ['{id_list}']"
            
            self._collection.delete(expr)
            self._collection.flush()
            
            logger.info(f"Deleted {len(ids)} documents from Milvus")
            
        except Exception as e:
            logger.error(f"Error deleting documents from Milvus: {e}")
            raise
    
    async def get_by_filter(self, filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get documents by metadata filter.
        
        Args:
            filter: Metadata filter dict
            
        Returns:
            List of matching documents
        """
        try:
            # Build filter expression
            conditions = []
            for key, value in filter.items():
                if isinstance(value, bool):
                    conditions.append(f"metadata['{key}'] == {str(value).lower()}")
                elif isinstance(value, str):
                    conditions.append(f"metadata['{key}'] == '{value}'")
                elif isinstance(value, (int, float)):
                    conditions.append(f"metadata['{key}'] == {value}")
            
            expr = " and ".join(conditions) if conditions else ""
            
            # Query documents
            results = self._collection.query(
                expr=expr,
                output_fields=["id", "page_content", "metadata"]
            )
            
            # Format results
            documents = []
            for result in results:
                documents.append({
                    "id": result.get("id"),
                    "page_content": result.get("page_content"),
                    "metadata": result.get("metadata", {})
                })
            
            logger.info(f"Found {len(documents)} documents matching filter")
            return documents
            
        except Exception as e:
            logger.error(f"Error getting documents by filter from Milvus: {e}")
            raise
    
    def close(self):
        """Close connection to Milvus."""
        try:
            connections = self._pymilvus['connections']
            if connections.has_connection("default"):
                connections.disconnect("default")
                logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.error(f"Error closing Milvus connection: {e}")
