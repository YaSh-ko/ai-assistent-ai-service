import pytest
import json
from tests.e2e.utils import create_test_session, wait_for_streaming

@pytest.mark.asyncio
async def test_streaming(client):
    user_id = "test_user_e2e"
    
    # 1. Create session
    session_id = await create_test_session(client, user_id)
    
    # 2. Open stream
    # Note: client.stream is used for streaming in httpx
    async with client.stream(
        "POST",
        f"/api/v1/chat/sessions/{session_id}/stream",
        json={"content": "Расскажи длинную историю."}
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["Content-Type"]
        
        # 3. Aggregate chunks
        full_content = await wait_for_streaming(response)
        
    # 4. Verify content
    assert len(full_content) > 0
    print(f"\nStreamed content length: {len(full_content)}")
    
    # 5. Verify history updated after stream
    history_res = await client.get(f"/api/v1/chat/sessions/{session_id}")
    history = history_res.json().get("history", [])
    assert any(msg["role"] == "assistant" and len(msg["content"]) > 0 for msg in history)
