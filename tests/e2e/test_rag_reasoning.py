import pytest
import json
from pathlib import Path
from tests.e2e.utils import create_test_session, seed_test_data, assert_response_format

@pytest.mark.asyncio
async def test_rag_reasoning(client):
    user_id = "test_user_e2e"
    fixtures_dir = Path(__file__).parent / "fixtures"
    
    # 1. Load and seed test data
    with open(fixtures_dir / "diary_entries.json", "r", encoding="utf-8") as f:
        diary_entries = json.load(f)
    
    # Ensure embeddings are 1024-dim if needed by the actual provider, 
    # but our mock/dummy in ChromaProvider might handle it.
    # In utils.py we seed to DB directly.
    await seed_test_data(user_id, diary_entries)
    
    # 2. Create session
    session_id = await create_test_session(client, user_id)
    
    # 3. Ask question that requires RAG
    # Question about Deleuze reading from fixtures
    response = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Что я читал вчера про Делёза?"}
    )
    
    # 4. Verify results
    assert response.status_code == 200
    data = response.json()
    assert_response_format(data, "chat_response")
    
    # Verify a non-empty response was returned (mock LLM returns fixed content)
    assert len(data["assistant_response"]) > 0
    
    # Verify reasoning was used (since it's a specific question about history/analysis)
    assert data["reasoning"]["type"] is not None
    print(f"\nReasoning used: {data['reasoning']['type']}")
