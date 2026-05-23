import os
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

# Force local connection for Chroma when running outside Docker
# os.environ["CHROMA_SERVER_HOST"] = "localhost" 
# os.environ["CHROMA_SERVER_PORT"] = "8001"

import asyncio
import httpx
import json
import logging
logging.basicConfig(level=logging.DEBUG)

from app.main import app
from fastapi.testclient import TestClient

def create_session(client, user_id):
    print(f"\n[1] Creating session for {user_id}...")
    response = client.post("/api/v1/chat/sessions", json={"user_id": user_id})
    response.raise_for_status()
    session_id = response.json()["session_id"]
    print(f"✅ Session created: {session_id}")
    return session_id

def send_sync_message(client, session_id):
    print("\n[2] Sending sync message...")
    msg_response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Привет! Как твои дела?"},
        timeout=30.0
    )
    msg_response.raise_for_status()
    data = msg_response.json()
    print(f"✅ Assistant response received: {data['assistant_response'][:100]}...")
    print(f"   Reasoning used: {data['reasoning']['type']}")
    print(f"   Complexity: {data['metadata']['complexity']}")

async def send_stream_message(session_id):
    print("\n[3] Sending stream message...")
    from httpx import ASGITransport
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as async_client:
        async with async_client.stream(
            "POST", 
            f"/api/v1/chat/sessions/{session_id}/stream",
            json={"content": "Расскажи какую-нибудь притчу о времени."},
            timeout=60.0
        ) as stream_response:
            stream_response.raise_for_status()
            print("✅ Stream started:")
            async for line in stream_response.aiter_lines():
                if line.startswith("data: "):
                    content = line[6:].strip()
                    if content == "[DONE]":
                        print("\n[Stream DONE]")
                    else:
                        try:
                            data = json.loads(content)
                            if data["type"] == "text":
                                print(data["data"]["content"], end="", flush=True)
                        except json.JSONDecodeError:
                            pass

def close_session(client, session_id):
    print("\n[4] Closing session...")
    close_response = client.post(f"/api/v1/chat/sessions/{session_id}/close")
    close_response.raise_for_status()
    print("✅ Session closed successfully.")

async def verify_e2e():
    from app.core.config import settings
    print(f"DEBUG: DATABASE_CONFIG host={settings.DATABASE_CONFIG['host']}, user={settings.DATABASE_CONFIG['user']}, db={settings.DATABASE_CONFIG['database']}")
    
    client = TestClient(app)
    print("=== Stage 6: E2E Integration Verification ===")
    
    try:
        session_id = create_session(client, "test_user_e2e")
        send_sync_message(client, session_id)
        await send_stream_message(session_id)
        close_session(client, session_id)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")

    print("\n=== E2E Verification Completed ===")

if __name__ == "__main__":
    asyncio.run(verify_e2e())
