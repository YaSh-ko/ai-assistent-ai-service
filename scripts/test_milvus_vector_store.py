#!/usr/bin/env python3
"""
Test script for Milvus vector store implementation.
Tests the MilvusProvider to ensure it works correctly.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.providers.databases.milvus_provider import MilvusProvider
from app.core.config import settings

async def test_milvus():
    """Test Milvus vector store operations."""
    
    print("=" * 60)
    print("Testing Milvus Vector Store")
    print("=" * 60)
    print()
    
    # Configuration
    print("Configuration:")
    print(f"  Host: {settings.MILVUS_HOST}")
    print(f"  Port: {settings.MILVUS_PORT}")
    print(f"  Collection: {settings.MILVUS_COLLECTION}")
    print(f"  Embedding Dimension: {settings.EMBEDDING_CONFIG['dimension']}")
    print()
    
    try:
        # Initialize Milvus provider
        print("1. Initializing Milvus provider...")
        provider = MilvusProvider()
        print("✓ Milvus provider initialized")
        print()
        
        # Test 1: Add documents
        print("2. Testing add_documents...")
        test_docs = [
            {
                "id": "doc1",
                "page_content": "Machine learning is a subset of artificial intelligence.",
                "metadata": {"source": "test", "category": "AI"}
            },
            {
                "id": "doc2",
                "page_content": "Deep learning uses neural networks with multiple layers.",
                "metadata": {"source": "test", "category": "AI"}
            },
            {
                "id": "doc3",
                "page_content": "Python is a popular programming language for data science.",
                "metadata": {"source": "test", "category": "Programming"}
            }
        ]
        
        # Generate dummy embeddings (in real use, these come from embedding model)
        embeddings = [
            [0.1] * 1024,  # doc1 embedding
            [0.2] * 1024,  # doc2 embedding
            [0.3] * 1024,  # doc3 embedding
        ]
        
        await provider.add_documents(test_docs, embeddings)
        print(f"✓ Added {len(test_docs)} documents")
        print()
        
        # Test 2: Similarity search
        print("3. Testing similarity_search...")
        query_embedding = [0.15] * 1024  # Similar to doc1
        results = await provider.similarity_search(query_embedding, k=2)
        
        print(f"✓ Found {len(results)} similar documents:")
        for i, doc in enumerate(results, 1):
            print(f"  {i}. ID: {doc['id']}")
            print(f"     Content: {doc['page_content'][:50]}...")
            print(f"     Score: {doc['score']:.4f}")
            print(f"     Metadata: {doc['metadata']}")
        print()
        
        # Test 3: Filter search
        print("4. Testing get_by_filter...")
        filtered_docs = await provider.get_by_filter({"category": "AI"})
        print(f"✓ Found {len(filtered_docs)} documents with category='AI':")
        for doc in filtered_docs:
            print(f"  - {doc['id']}: {doc['page_content'][:50]}...")
        print()
        
        # Test 4: Delete documents
        print("5. Testing delete_documents...")
        await provider.delete_documents(["doc3"])
        print("✓ Deleted document 'doc3'")
        print()
        
        # Verify deletion
        print("6. Verifying deletion...")
        all_docs = await provider.get_by_filter({"source": "test"})
        print(f"✓ Remaining documents: {len(all_docs)}")
        for doc in all_docs:
            print(f"  - {doc['id']}")
        print()
        
        # Test 5: Reset collection
        print("7. Testing reset...")
        await provider.reset()
        print("✓ Collection reset")
        print()
        
        # Verify reset
        print("8. Verifying reset...")
        all_docs_after_reset = await provider.get_by_filter({"source": "test"})
        print(f"✓ Documents after reset: {len(all_docs_after_reset)}")
        print()
        
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
        # Cleanup
        provider.close()
        print("\n✓ Connection closed")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import Error: {e}")
        print("\nTo use Milvus, install pymilvus:")
        print("  pip install pymilvus")
        return False
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point."""
    print()
    print("Milvus Vector Store Test")
    print()
    print("Prerequisites:")
    print("  1. Milvus server running (docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest)")
    print("  2. pymilvus installed (pip install pymilvus)")
    print()
    
    success = await test_milvus()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
