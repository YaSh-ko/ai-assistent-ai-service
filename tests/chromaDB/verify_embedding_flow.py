import asyncio
import os
import sys
from typing import List, Dict, Any

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.chunking_service import ChunkingService
from app.providers.databases.chroma_provider import ChromaProvider
from app.providers.embeddings.gigachat_embeddings import GigaChatEmbeddings
from app.data_access.repositories.embedding_repository import EmbeddingRepository
from app.services.embedding_service import EmbeddingService
from app.core.config import settings

async def main():
    import os
    from dotenv import load_dotenv
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("http.client").setLevel(logging.DEBUG)

    # Load environment variables
    # Load environment variables
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_path, override=True)

    # Debug: Check what's being loaded
    print("=== DEBUG: Environment Variables ===")
    print(f"GIGACHAT_CREDENTIALS from .env: {settings.GIGACHAT_CREDENTIALS}")
    print(f"Credential length: {len(settings.GIGACHAT_CREDENTIALS)}")
    print("====================================")
    
    print("Starting verification of embedding flow...")

    # 1. Initialize components
    chunking_service = ChunkingService()
    chroma_provider = ChromaProvider()
    embeddings_provider = GigaChatEmbeddings()
    embedding_repository = EmbeddingRepository(chroma_provider)
    embedding_service = EmbeddingService(chunking_service, embeddings_provider, embedding_repository)

    # 2. Reset DB
    print("Resetting ChromaDB...")
    await embedding_repository.reset()

    # 3. Simulate Chat History
    chat_history = """
User: Hello, I want to record a diary entry.
AI: Sure, what would you like to say?
User: Today was a great day. I learned about vector databases.
AI: That sounds interesting! Tell me more.
User: They are really useful for semantic search. I'm using ChromaDB.
    """
    metadata = {"session_id": "test_session", "user_id": "test_user"}

    # 4. Process Text
    print("Processing text (Chunking -> Embedding -> Storage)...")
    await embedding_service.process_text(chat_history, metadata)

    # 5. Verify Storage via Search
    print("Verifying storage via search...")
    query_embedding = await embeddings_provider.embed_query("vector databases")
    results = await chroma_provider.similarity_search(query_embedding, k=2)
    
    print(f"Found {len(results)} results:")
    for res in results:
        print(f"- {res['page_content']} (Metadata: {res['metadata']})")

    # Check if results contain expected content
    assert len(results) > 0
    assert any("vector databases" in res["page_content"] for res in results)
    
    print("\nVerification SUCCESS!")

if __name__ == "__main__":
    asyncio.run(main())
