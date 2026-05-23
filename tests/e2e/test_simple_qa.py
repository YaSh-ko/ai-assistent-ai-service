import pytest
from tests.e2e.utils import create_test_session, assert_response_format

@pytest.mark.asyncio
async def test_simple_qa(client):
    user_id = "test_user_e2e"
    
    # 1. Create session
    session_id = await create_test_session(client, user_id)
    assert session_id is not None
    
    # 2. Send simple question
    response = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Привет! Как тебя зовут?"}
    )
    
    # 3. Verify response
    assert response.status_code == 200
    data = response.json()
    assert_response_format(data, "chat_response")
    assert "assistant_response" in data
    assert len(data["assistant_response"]) > 0
    # Simple questions might be routed to vLLM or GigaChat depending on classifier
    print(f"\nAssistant response: {data['assistant_response'][:100]}...")
