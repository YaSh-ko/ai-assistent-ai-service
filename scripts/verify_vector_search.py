import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.providers.databases.chroma_provider import ChromaProvider
from app.providers.search.vector_search_provider import VectorSearchProvider

async def main():
    print("Initializing ChromaDB connection...")
    chroma = ChromaProvider()
    vector_search = VectorSearchProvider(chroma)
    
    try:
        # 1. Reset collection to start fresh
        print("\nResetting ChromaDB collection...")
        await chroma.reset()
        
        # 2. Insert sample documents with embeddings
        print("\nInserting sample documents...")
        user_id = "test_user_vector"
        
        documents = [
            {
                "id": "doc1",
                "page_content": "Тренировка в зале была очень интенсивной",
                "metadata": {"user_id": user_id, "entry_id": "entry1", "timestamp": "2024-01-01"}
            },
            {
                "id": "doc2",
                "page_content": "Купил новые кроссовки для бега",
                "metadata": {"user_id": user_id, "entry_id": "entry2", "timestamp": "2024-01-02"}
            },
            {
                "id": "doc3",
                "page_content": "Сегодня отдыхал и смотрел фильм",
                "metadata": {"user_id": user_id, "entry_id": "entry3", "timestamp": "2024-01-03"}
            }
        ]
        
        # Create dummy embeddings (orthogonal for clear distinction)
        # Doc1: [1, 0, 0, ...]
        # Doc2: [0, 1, 0, ...]
        # Doc3: [0, 0, 1, ...]
        
        emb1 = [0.0] * 1024
        emb1[0] = 1.0
        
        emb2 = [0.0] * 1024
        emb2[1] = 1.0
        
        emb3 = [0.0] * 1024
        emb3[2] = 1.0
        
        embeddings = [emb1, emb2, emb3]
        
        await chroma.add_documents(documents, embeddings)
        print("Sample documents inserted.")
        
        # 3. Perform vector search
        # Query matches Doc1
        query_embedding = [0.0] * 1024
        query_embedding[0] = 1.0
        print("\nPerforming vector search...")
        results = await vector_search.search(query_embedding=query_embedding, top_k=3)
        
        print(f"\nFound {len(results)} results:")
        for i, r in enumerate(results, 1):
            print(f"{i}. Content: {r['page_content']}")
            print(f"   Metadata: {r['metadata']}")
            print(f"   Score: {r.get('score', 'N/A')}")
            print("-" * 50)
        
        # 4. Test with filter
        print("\nPerforming filtered search (by user_id)...")
        results_filtered = await vector_search.search(
            query_embedding=query_embedding, 
            top_k=2,
            filter={"user_id": user_id}
        )
        
        print(f"Found {len(results_filtered)} filtered results.")
        
        # 5. Cleanup
        print("\nCleaning up...")
        await chroma.reset()
        print("Cleanup done.")
        
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
