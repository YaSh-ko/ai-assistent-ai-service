import asyncio
import os
import sys
from dotenv import load_dotenv
from datetime import date

# 1. Load environment variables FIRST
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
env_path = os.path.join(project_root, ".env")
print(f"Loading .env from: {env_path}")
load_dotenv(env_path, override=True)

# Add the project root to sys.path
sys.path.append(project_root)

# Override port for testing (docker-compose maps 5433:5432)
from app.core.config import settings
current_url = settings.POSTGRES_URL
print(f"Original POSTGRES_URL: {current_url}")

if not current_url:
    print("POSTGRES_URL is empty. Constructing from env vars...")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db = os.getenv("POSTGRES_DB", "postgres")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = "5433" # Force 5433 for testing
    settings.POSTGRES_URL = f"postgresql://{user}:{password}@{host}:{port}/{db}"
elif "5432" in current_url:
    settings.POSTGRES_URL = current_url.replace("5432", "5433")
elif "@postgres" in current_url:
    # If using internal docker name, replace with localhost:5433
    settings.POSTGRES_URL = current_url.replace("@postgres", "@localhost:5433")
else:
    # Try to append port if missing or replace host
    # Assuming standard format postgresql://user:pass@host:port/db or ...@host/db
    if "@localhost" in current_url and ":5433" not in current_url:
         settings.POSTGRES_URL = current_url.replace("@localhost", "@localhost:5433")

print(f"Updated POSTGRES_URL: {settings.POSTGRES_URL}")

from app.factory.database_factory import DatabaseFactory
from app.factory.search_factory import SearchFactory
from app.services.embedding_service import EmbeddingService
from app.services.chunking_service import ChunkingService
from app.data_access.repositories.dal import DataAccessLayer
from app.data_access.repositories.embedding_repository import EmbeddingRepository
from app.providers.embeddings.gigachat_embeddings import GigaChatEmbeddings
from app.providers.databases.chroma_provider import ChromaProvider
from app.chains.rag_chain import RAGChain
from app.core.config import settings
import shutil

async def main():
    print("Starting RAG Chain Verification...")

    # 0. Clean up previous DB
    if os.path.exists(settings.CHROMA_DB_PATH):
        print(f"Cleaning up existing DB at {settings.CHROMA_DB_PATH}...")
        shutil.rmtree(settings.CHROMA_DB_PATH)

    # 1. Initialize Components
    print("Initializing components...")
    try:
        # DB & DAL
        dal = await DatabaseFactory.create_dal_async()
        
        # Repositories (access from DAL)
        chat_session_repo = dal.chat_session_repo
        entry_repo = dal.entry_repo
        entry_thread_repo = dal.entry_thread_repo
        embedding_repo = dal.embedding_repo
        
        # Vector Store (Chroma) - accessed via embedding_repo or factory
        # We need chroma_provider for SearchFactory
        # embedding_repo.vector_store is the provider
        chroma_provider = embedding_repo._vector_store
        
        # Services
        embeddings_provider = GigaChatEmbeddings()
        chunking_service = ChunkingService()
        embedding_service = EmbeddingService(
            chunking_service=chunking_service,
            embeddings_provider=embeddings_provider,
            embedding_repository=embedding_repo
        )
        
        # Search Provider
        # We need the pool from the DAL's repositories.
        # All postgres repos share the same pool.
        postgres_pool = entry_repo.db_pool
        
        search_provider = SearchFactory.create_hybrid_provider(
            postgres_pool=postgres_pool,
            vector_store=chroma_provider
        )
        
        # RAG Chain
        rag_chain = RAGChain(dal, embedding_service, search_provider)
        graph = rag_chain.build_graph()
        
        print("Components initialized successfully.")
        
        # 2. Seed Data (Simulate previous entries)
        print("\nSeeding data...")
        user_id = "rag_test_user"
        thread_id = "rag_test_thread"
        
        # Create user if not exists
        try:
            async with entry_repo.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO "user" (id, name, email, "emailVerified", "createdAt", "updatedAt")
                    VALUES ($1, $2, $3, $4, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    user_id, "Test User", "rag_test_user@example.com", True
                )
            print(f"User {user_id} created/verified.")
        except Exception as e:
            print(f"Error creating user: {e}")
            # Try with minimal fields if schema is different
            try:
                 async with entry_repo.db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO "user" (id, name, email, "emailVerified")
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        user_id, "Test User", "rag_test_user@example.com", True
                    )
            except Exception as e2:
                print(f"Error creating user (retry): {e2}")
                # If email conflict, we might want to update the existing user or ignore
                if "unique constraint" in str(e2) and "email" in str(e2):
                     print("User with email already exists, proceeding...")
                else:
                     raise e2
        
        seed_entry = {
            "title": "Learning RAG",
            "description": "RAG stands for Retrieval-Augmented Generation. It combines retrieval and generation.",
            "event_date": date(2023, 10, 27)
        }
        
        # Generate embedding for seed
        seed_text = f"{seed_entry['title']}\n{seed_entry['description']}"
        seed_embedding = await embeddings_provider.embed_query(seed_text)
        
        await dal.save_entry_with_embedding(
            user_id=user_id,
            title=seed_entry["title"],
            description=seed_entry["description"],
            event_date=seed_entry["event_date"],
            thread_id=thread_id,
            embedding=seed_embedding
        )
        print("Data seeded.")
        
        # 3. Run Chain
        print("\nRunning RAG Chain...")
        initial_state = {
            "question": "What does RAG stand for?",
            "user_id": user_id,
            "thread_id": thread_id,
            "session_id": "rag_test_session",
            "extracted_events": [
                {
                    "title": "RAG Verification",
                    "description": "Verified that RAG chain works correctly.",
                    "event_date": "2023-10-28"
                }
            ]
        }
        
        result = await graph.ainvoke(initial_state)
        
        print("\n=== RAG Chain Result ===")
        print(f"Question: {result['question']}")
        print(f"Context Retrieved:\n{result.get('context', 'No context')}")
        print(f"Answer: {result.get('answer', 'No answer')}")
        
        # 4. Verify New Event Saved
        print("\nVerifying new event saved...")
        # We can check by searching for it
        verification_query = "RAG Verification"
        verification_embedding = await embeddings_provider.embed_query(verification_query)
        
        search_results = await search_provider.search(
            query=verification_query,
            query_embedding=verification_embedding,
            k=1,
            filter={"user_id": user_id}
        )
        
        if search_results and "Verified that RAG chain works correctly" in search_results[0].get("description", ""):
            print("SUCCESS: New event found in search results.")
        else:
            print("FAILURE: New event NOT found in search results.")
            print(f"Search results: {search_results}")

    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'postgres_provider' in locals():
            await postgres_provider.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
