import asyncio
import os
import uuid
from dotenv import load_dotenv

# Load .env explicitly
load_dotenv()

import sys
# Add project root to sys.path to allow importing app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.providers.databases.postgres_provider import PostgresProvider
from app.providers.search.bm25_provider import BM25Provider

async def main():
    print("=" * 60)
    print("BM25 Search Verification with Custom Parameters")
    print("=" * 60)
    
    # Setup
    if not settings.POSTGRES_URL:
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5433")
        db = os.getenv("POSTGRES_DB", "postgres")
        settings.POSTGRES_URL = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    
    provider = PostgresProvider()
    await provider.connect()
    
    # Insert test data
    user_id = "test_user_bm25_params"
    
    # Clean up first
    async with provider.pool.acquire() as conn:
        # Ensure user exists
        await conn.execute("""
            INSERT INTO "user" (id, name, email, "emailVerified", "createdAt", "updatedAt")
            VALUES ($1, 'Test User', 'test@example.com', false, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """, user_id)
        
        await conn.execute("DELETE FROM entries WHERE user_id = $1", user_id)
        
        # Insert documents with varying lengths and term frequencies
        # Doc 1: Short, high frequency of "test"
        await conn.execute("""
            INSERT INTO entries (id, user_id, title, description, event_date)
            VALUES ($1, $2, $3, $4, NOW())
        """, str(uuid.uuid4()), user_id, "Test Test", "Test term frequency",)
        
        # Doc 2: Long, low frequency of "test"
        await conn.execute("""
            INSERT INTO entries (id, user_id, title, description, event_date)
            VALUES ($1, $2, $3, $4, NOW())
        """, str(uuid.uuid4()), user_id, "Test Document", "This is a much longer document that contains the word test only once but has many other words to increase the document length significantly.")

    bm25 = BM25Provider(provider.pool)
    query = "test"
    
    try:
        # Test 1: Default parameters (k1=1.5, b=0.75)
        print("\n1. Testing with Default Parameters (k1=1.5, b=0.75)")
        settings.SEARCH_CONFIG["bm25_k1"] = 1.5
        settings.SEARCH_CONFIG["bm25_b"] = 0.75
        
        results_default = await bm25.search(query, user_id=user_id, top_k=5)
        for r in results_default:
            print(f"   - {r['title']}: {r['bm25_score']:.4f}")
            
        # Test 2: High b (b=1.0) - Full length normalization
        # Longer documents should be penalized more
        print("\n2. Testing with High b (b=1.0)")
        settings.SEARCH_CONFIG["bm25_b"] = 1.0
        
        results_high_b = await bm25.search(query, user_id=user_id, top_k=5)
        for r in results_high_b:
            print(f"   - {r['title']}: {r['bm25_score']:.4f}")
            
        # Test 3: Low k1 (k1=0.1) - Low saturation
        # TF impact should be reduced
        print("\n3. Testing with Low k1 (k1=0.1)")
        settings.SEARCH_CONFIG["bm25_k1"] = 0.1
        settings.SEARCH_CONFIG["bm25_b"] = 0.75 # Reset b
        
        results_low_k1 = await bm25.search(query, user_id=user_id, top_k=5)
        for r in results_low_k1:
            print(f"   - {r['title']}: {r['bm25_score']:.4f}")
        # 4. Cleanup
        async with provider.pool.acquire() as conn:
            await conn.execute("DELETE FROM entries WHERE user_id = $1", user_id)
        print("\nCleanup done.")
        
    finally:
        await provider.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
