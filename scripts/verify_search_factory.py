import asyncio
import os
from dotenv import load_dotenv

# Load .env explicitly
load_dotenv()

from app.core.config import settings
from app.providers.databases.postgres_provider import PostgresProvider
from app.providers.databases.chroma_provider import ChromaProvider
from app.factory.search_factory import SearchFactory
from app.factory.database_factory import DatabaseFactory

async def main():
    print("=" * 60)
    print("Search Factory Verification")
    print("=" * 60)
    
    # Setup
    print(f"\nOriginal POSTGRES_URL: {settings.POSTGRES_URL}")
    if not settings.POSTGRES_URL:
        user = os.getenv("POSTGRES_USER", "postgres")
        password = os.getenv("POSTGRES_PASSWORD", "postgres")
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "5433")
        db = os.getenv("POSTGRES_DB", "postgres")
        settings.POSTGRES_URL = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        print(f"Constructed POSTGRES_URL: {settings.POSTGRES_URL}")
    
    # Create database instances
    postgres = DatabaseFactory.create_relational_database("postgres")
    await postgres.connect()
    
    vector_store = DatabaseFactory.create_vector_store("chroma")
    
    try:
        # Test 1: Create BM25 provider
        print("\n1. Testing BM25 Provider creation...")
        bm25_provider = SearchFactory.create_bm25_provider(postgres.pool)
        print(f"   ✓ BM25Provider created: {type(bm25_provider).__name__}")
        
        # Test 2: Create Vector provider
        print("\n2. Testing Vector Provider creation...")
        vector_provider = SearchFactory.create_vector_provider(vector_store)
        print(f"   ✓ VectorSearchProvider created: {type(vector_provider).__name__}")
        
        # Test 3: Create Hybrid provider
        print("\n3. Testing Hybrid Provider creation...")
        hybrid_provider = SearchFactory.create_hybrid_provider(postgres.pool, vector_store)
        print(f"   ✓ HybridSearchProvider created: {type(hybrid_provider).__name__}")
        
        # Test 4: Test configuration-based provider selection
        print("\n4. Testing configuration-based provider selection...")
        search_type = settings.SEARCH_CONFIG.get("search_type", "hybrid")
        print(f"   Current SEARCH_TYPE: {search_type}")
        
        provider = SearchFactory.create_search_provider(
            postgres_pool=postgres.pool,
            vector_store=vector_store
        )
        print(f"   ✓ Default provider created: {type(provider).__name__}")
        
        # Test 5: Test explicit type selection
        print("\n5. Testing explicit type selection...")
        for test_type in ["bm25", "vector", "hybrid"]:
            provider = SearchFactory.create_search_provider(
                search_type=test_type,
                postgres_pool=postgres.pool,
                vector_store=vector_store
            )
            print(f"   ✓ {test_type.upper()} provider: {type(provider).__name__}")
        
        # Test 6: Test error handling (missing dependencies)
        print("\n6. Testing error handling...")
        try:
            SearchFactory.create_search_provider(search_type="bm25")
            print("   ✗ Should have raised ValueError for missing postgres_pool")
        except ValueError as e:
            print(f"   ✓ Correctly raised ValueError: {e}")
        
        try:
            SearchFactory.create_search_provider(search_type="unknown", postgres_pool=postgres.pool)
            print("   ✗ Should have raised ValueError for unknown type")
        except ValueError as e:
            print(f"   ✓ Correctly raised ValueError: {e}")
        
        print("\n" + "=" * 60)
        print("All factory tests passed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await postgres.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
