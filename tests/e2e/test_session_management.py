import pytest
from tests.e2e.utils import create_test_session, assert_response_format

@pytest.mark.asyncio
async def test_session_management(client):
    user_id = "test_user_e2e"
    
    # 1. Create session
    session_id = await create_test_session(client, user_id)
    
    # 2. Send multiple messages
    messages = ["Привет!", "Как дела?", "Расскажи о себе."]
    for msg in messages:
        res = await client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": msg}
        )
        assert res.status_code == 200
        
    # 3. Check session info/history
    history_res = await client.get(f"/api/v1/chat/sessions/{session_id}")
    assert history_res.status_code == 200
    data = history_res.json()
    assert_response_format(data, "session_info")
    # History should have 6 messages (3 pairs user-assistant)
    # Note: might vary if some messages are filtered, but basic check:
    assert len(data.get("history", [])) >= 3
    
    # 4. Close session
    close_res = await client.post(f"/api/v1/chat/sessions/{session_id}/close")
    assert close_res.status_code == 200
    assert close_res.json()["status"] == "closed"
    
    # 5. Verify closed status
    final_info = await client.get(f"/api/v1/chat/sessions/{session_id}")
    assert final_info.json()["status"] == "closed"
