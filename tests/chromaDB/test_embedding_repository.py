import pytest
from uuid import uuid4
from app.data_access.repositories.embedding_repository import EmbeddingRepository

@pytest.mark.asyncio
async def test_embedding_lifecycle(chroma_client):
    """Полный жизненный цикл embedding"""
    # Assuming chroma_client is an instance of IVectorStore (e.g. ChromaProvider)
    # If chroma_client is the raw chromadb client, we might need to wrap it or mock IVectorStore.
    # The user's example uses EmbeddingRepository(chroma_client).
    # This implies chroma_client in the test should be an IVectorStore implementation.
    
    repo = EmbeddingRepository(chroma_client)
    entry_id = str(uuid4())
    
    # ADD
    await repo.add_embedding(
        document_id=entry_id,
        embedding=[0.1, 0.2, 0.3] * 512,  # 1536-мерный вектор (adjusted to match dummy embedding size if needed)
        metadata={
            "entry_id": entry_id,
            "user_id": "user_123",
            "title": "Test"
        },
        page_content="Test content"
    )
    
    # GET BY ENTRY_ID
    result = await repo.get_by_entry_id(entry_id)
    assert result is not None
    
    # UPDATE
    await repo.update_embedding(
        document_id=entry_id,
        new_embedding=[0.2, 0.3, 0.4] * 512,
        new_metadata={
            "entry_id": entry_id,
            "user_id": "user_123",
            "title": "Updated"
        },
        new_page_content="Updated content"
    )
    
    # SEARCH BY USER
    results = await repo.search_by_user(
        user_id="user_123",
        query_embedding=[0.15, 0.25, 0.35] * 512,
        k=5
    )
    assert len(results) > 0
    
    # COUNT
    count = await repo.count_by_user("user_123")
    assert count >= 1
    
    # DELETE
    await repo.delete_embedding(entry_id)
    deleted = await repo.get_by_entry_id(entry_id)
    assert deleted is None
