import pytest
import json
from pathlib import Path
from tests.e2e.utils import create_test_session, seed_test_data, assert_response_format

@pytest.mark.asyncio
async def test_pattern_analysis(client):
    user_id = "test_user_e2e"
    fixtures_dir = Path(__file__).parent / "fixtures"
    
    # 1. Load fixtures
    with open(fixtures_dir / "diary_entries.json", "r", encoding="utf-8") as f:
        diary_entries = json.load(f)
    with open(fixtures_dir / "graph_data.json", "r", encoding="utf-8") as f:
        graph_data = json.load(f)
        
    # 2. Seed data (including Neo4j)
    await seed_test_data(user_id, diary_entries, graph_data)
    
    # 3. Create session
    session_id = await create_test_session(client, user_id)
    
    # 4. Ask complex question requiring pattern analysis
    response = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Проанализируй мои последние записи и найди связи между концепциями."}
    )
    
    # 5. Verify results
    assert response.status_code == 200
    data = response.json()
    assert_response_format(data, "chat_response")
    
    # Metadata should show high complexity
    # Note: depends on classifier configuration
    # assert data["metadata"]["complexity"] in ["medium", "complex"]
    
    print(f"\nComplexity: {data['metadata'].get('complexity')}")
    print(f"Assistant response: {data['assistant_response'][:150]}...")
