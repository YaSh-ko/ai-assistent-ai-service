import asyncio
import os
import uuid
from dotenv import load_dotenv

# Load .env explicitly
load_dotenv()

import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.providers.databases.postgres_provider import PostgresProvider
from app.providers.databases.chroma_provider import ChromaProvider
from app.providers.search.bm25_provider import BM25Provider
from app.providers.search.vector_search_provider import VectorSearchProvider
from app.providers.search.hybrid_search_provider import HybridSearchProvider

async def main():
    # Setup database connections
    print(f"Original POSTGRES_URL: {settings.POSTGRES_URL}")
    if not settings.POSTGRES_URL:
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5433")
        db = os.getenv("POSTGRES_DB", "postgres")
        settings.POSTGRES_URL = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        print(f"Constructed POSTGRES_URL: {settings.POSTGRES_URL}")
    
    postgres = PostgresProvider()
    await postgres.connect()
    
    chroma = ChromaProvider()
    
    # Initialize search providers
    bm25 = BM25Provider(postgres.pool)
    vector_search = VectorSearchProvider(chroma)
    hybrid_search = HybridSearchProvider(bm25, vector_search)
    
    try:
        # 1. Setup test data
        user_id = "test_user_hybrid"
        
        # Generate valid UUIDs for entries
        entry1_id = str(uuid.uuid4())
        entry2_id = str(uuid.uuid4())
        entry3_id = str(uuid.uuid4())
        
        # Insert data into PostgreSQL
        print("\nInserting test data into PostgreSQL...")
        
        # Ensure user exists
        await postgres.execute("""
            INSERT INTO "user" (id, name, email, "emailVerified", "createdAt", "updatedAt")
            VALUES ($1, 'Test User Hybrid', 'hybrid@example.com', false, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """, {"id": user_id})

        await postgres.execute("""
            INSERT INTO entries (id, user_id, event_date, title, description)
            VALUES 
            ($1, $2, NOW(), 'Тренировка в зале', 'Сегодня была интенсивная тренировка в зале'),
            ($3, $2, NOW(), 'Покупка кроссовок', 'Купил новые кроссовки для бега'),
            ($4, $2, NOW(), 'Отдых дома', 'Весь день отдыхал и смотрел фильмы')
            ON CONFLICT DO NOTHING
        """, {
            "id1": entry1_id,
            "user_id": user_id,
            "id2": entry2_id,
            "id3": entry3_id
        })
        
        # Reset and insert data into ChromaDB
        print("Resetting ChromaDB and inserting test data...")
        await chroma.reset()
        
        documents = [
            {
                "id": "doc1",
                "page_content": "Сегодня была интенсивная тренировка в зале",
                "metadata": {"user_id": user_id, "entry_id": entry1_id, "timestamp": "2024-01-01"}
            },
            {
                "id": "doc2",
                "page_content": "Купил новые кроссовки для бега",
                "metadata": {"user_id": user_id, "entry_id": entry2_id, "timestamp": "2024-01-02"}
            },
            {
                "id": "doc3",
                "page_content": "Весь день отдыхал и смотрел фильмы",
                "metadata": {"user_id": user_id, "entry_id": entry3_id, "timestamp": "2024-01-03"}
            }
        ]
        
        # Create embeddings (dummy, but make them different)
        embeddings = [
            [0.9] * 1024,  # doc1 - training related
            [0.5] * 1024,  # doc2 - shoes
            [0.1] * 1024,  # doc3 - rest
        ]
        
        await chroma.add_documents(documents, embeddings)
        print("Test data inserted.")
        
        # 2. Perform hybrid search
        query = "тренировка"
        query_embedding = [0.9] * 1024  # Should match doc1/entry1 best
        
        print(f"\n{'='*60}")
        print(f"Performing hybrid search for: '{query}'")
        print(f"BM25 weight: {settings.SEARCH_CONFIG['bm25_weight']}")
        print(f"Vector weight: {settings.SEARCH_CONFIG['vector_weight']}")
        print(f"{'='*60}")
        
        results = await hybrid_search.search(
            query=query,
            query_embedding=query_embedding,
            top_k=3,
            user_id=user_id
        )
        
        print(f"\nFound {len(results)} hybrid search results:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. ID: {r.get('id')}")
            print(f"   Title: {r.get('title', 'N/A')}")
            print(f"   Description: {r.get('description', r.get('page_content', 'N/A'))}")
            print(f"   BM25 Score: {r.get('bm25_score', 0):.4f} (normalized: {r.get('bm25_normalized', 0):.4f})")
            print(f"   Vector Score: {r.get('vector_score', 0):.4f} (normalized: {r.get('vector_normalized', 0):.4f})")
            print(f"   Final Score: {r.get('final_score', 0):.4f}")
            print(f"   Source: {r.get('source', 'unknown')}")
            print("-" * 60)
        
        # 3. Cleanup
        print("\nCleaning up...")
        await postgres.execute("DELETE FROM entries WHERE user_id = $1", {"user_id": user_id})
        await postgres.execute("DELETE FROM \"user\" WHERE id = $1", {"id": user_id})
        await chroma.reset()
        print("Cleanup done.")
        
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await postgres.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
