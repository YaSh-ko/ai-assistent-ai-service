from typing import AsyncGenerator, Optional
import logging
import asyncio
from app.factory.database_factory import DatabaseFactory
from app.data_access.postgresql.chat_session_repository import ChatSessionRepository
from app.services.session_manager import SessionManager
from app.services.detector_service import DetectorService
from app.services.entity_index_service import EntityIndexService
from app.providers.databases.postgres_provider import PostgresProvider
from app.chains.rag_chain import RAGChain
from app.services.embedding_service import EmbeddingService
from app.services.chunking_service import ChunkingService
from app.services.llm_service import LLMService
from app.services.reasoning_service import ReasoningService
from app.providers.embeddings.gigachat_embeddings import GigaChatEmbeddings
from app.providers.search.bm25_provider import BM25Provider
from app.providers.search.vector_search_provider import VectorSearchProvider
from app.providers.search.hybrid_search_provider import HybridSearchProvider
from app.providers.search.reranker_provider import RerankerProvider
from app.data_access.neo4j.graph_repository import GraphRepository
from app.services.pii_service import PIIService
from app.data_access.repositories.dal import DataAccessLayer

logger = logging.getLogger(__name__)

# Shared instances for singletons
_llm_service = None
_reasoning_service = None
_pii_service = None
_session_manager = None
_rag_chain = None
_dal = None
_detector_service = None

# Initialization locks
_llm_lock = asyncio.Lock()
_reasoning_lock = asyncio.Lock()
_pii_lock = asyncio.Lock()
_session_manager_lock = asyncio.Lock()
_rag_chain_lock = asyncio.Lock()
_dal_lock = asyncio.Lock()
_detector_service_lock = asyncio.Lock()

async def get_llm_service() -> LLMService:
    global _llm_service
    async with _llm_lock:
        if _llm_service is None:
            _llm_service = LLMService()
    return _llm_service

async def get_reasoning_service() -> ReasoningService:
    global _reasoning_service
    async with _reasoning_lock:
        if _reasoning_service is None:
            _reasoning_service = ReasoningService()
    return _reasoning_service

async def get_pii_service() -> PIIService:
    global _pii_service
    async with _pii_lock:
        if _pii_service is None:
            _pii_service = PIIService()
    return _pii_service

async def get_dal_async() -> DataAccessLayer:
    """Dependency to get the DataAccessLayer singleton."""
    global _dal
    async with _dal_lock:
        if _dal is None:
            try:
                _dal = await DatabaseFactory.create_dal_async()
            except Exception as e:
                logger.error(f"DAL initialization failed: {e}")
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=503,
                    detail="Database unavailable. Check that PostgreSQL is running and DATABASE_URL is correct."
                )
    return _dal

async def get_session_manager() -> SessionManager:
    """Dependency to get SessionManager singleton."""
    global _session_manager
    async with _session_manager_lock:
        if _session_manager is None:
            provider = DatabaseFactory.create_relational_database()
            
            if isinstance(provider, PostgresProvider):
                if not provider.pool:
                    try:
                        await provider.connect()
                    except Exception as e:
                        logger.error(f"PostgreSQL connection failed: {e}")
                        from fastapi import HTTPException
                        raise HTTPException(
                            status_code=503,
                            detail="Database unavailable. Check that PostgreSQL is running and DATABASE_URL is correct."
                        )
                
                repo = ChatSessionRepository(provider)
                _session_manager = SessionManager(repo)
            else:
                logger.error("SessionManager requires PostgresProvider")
                raise RuntimeError("SessionManager requires PostgresProvider")
    return _session_manager

async def get_detector_service() -> DetectorService:
    """Dependency to get DetectorService singleton."""
    global _detector_service
    async with _detector_service_lock:
        if _detector_service is None:
            session_manager = await get_session_manager()
            postgres_provider = DatabaseFactory.create_relational_database()
            if not postgres_provider.pool:
                await postgres_provider.connect()
            embeddings_provider = GigaChatEmbeddings()
            entity_index = EntityIndexService(postgres_provider, embeddings_provider)
            _detector_service = DetectorService(
                session_manager, entity_index=entity_index,
            )
    return _detector_service


async def get_rag_chain() -> RAGChain:
    """Dependency to get RAGChain singleton with full integration."""
    global _rag_chain
    async with _rag_chain_lock:
        if _rag_chain is None:
            # 1. Database & DAL
            dal = await get_dal_async()
            
            # 2. Search Providers
            # Postgres for BM25 (reuse pool from provider)
            postgres_provider = DatabaseFactory.create_relational_database()
            if not postgres_provider.pool:
                await postgres_provider.connect()
                
            # Vector store (Chroma)
            vector_store = DatabaseFactory.create_vector_store("chroma")
            
            # Instantiate search providers
            bm25_provider = BM25Provider(postgres_provider)
            vector_provider = VectorSearchProvider(vector_store)
            hybrid_search_provider = HybridSearchProvider(bm25_provider, vector_provider)
            
            # 3. Graph Repository (Neo4j)
            graph_repository = None
            try:
                graph_db = await DatabaseFactory.create_graph_database()
                graph_repository = GraphRepository(graph_db)
            except Exception as e:
                logger.warning(f"Neo4j unavailable, graph search disabled: {e}")
            
            # 4. Services
            chunking_service = ChunkingService()
            embeddings_provider = GigaChatEmbeddings() # Real GigaChat embeddings
            
            embedding_service = EmbeddingService(
                chunking_service=chunking_service,
                embeddings_provider=embeddings_provider,
                embedding_repository=dal.embedding_repo
            )
            
            llm_service = await get_llm_service()
            reasoning_service = await get_reasoning_service()
            reranker_provider = RerankerProvider(llm_service)
            pii_service = await get_pii_service()
            
            # 5. Create RAGChain
            _rag_chain = RAGChain(
                dal=dal,
                embedding_service=embedding_service,
                llm_service=llm_service,
                reasoning_service=reasoning_service,
                hybrid_search_provider=hybrid_search_provider,
                reranker_provider=reranker_provider,
                graph_repository=graph_repository,
                pii_service=pii_service
            )
            
    return _rag_chain
