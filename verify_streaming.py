import asyncio
import json
import httpx

async def verify_streaming():
    base_url = "http://localhost:8000/api/v1"
    
    # 1. Create Session
    async with httpx.AsyncClient() as client:
        print("Creating session...")
        response = await client.post(f"{base_url}/chat/sessions", json={"user_id": "test_user"})
        if response.status_code != 200:
            print(f"Failed to create session: {response.text}")
            return
        
        session_id = response.json()["session_id"]
        print(f"Session created: {session_id}")

        # 2. Send Message and Stream
        print("Sending message and streaming response...")
        async with client.stream(
            "POST", 
            f"{base_url}/chat/sessions/{session_id}/messages", 
            json={"content": "Hello, tell me a short joke.", "role": "user"}
        ) as response:
            
            if response.status_code != 200:
                print(f"Failed to stream: {response.status_code}")
                # Read error body
                print(await response.aread())
                return

            print("Stream started...")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        print("\nStream finished.")
                        break
                    
                    try:
                        chunk = json.loads(data)
                        if chunk["type"] == "text":
                            print(chunk["data"]["content"], end="", flush=True)
                        elif chunk["type"] == "error":
                            print(f"\nError in stream: {chunk['data']['message']}")
                    except json.JSONDecodeError:
                        print(f"\nFailed to parse: {data}")

if __name__ == "__main__":
    # Note: This requires the server to be running. 
    # Since we can't easily start the server and run this script in the same environment without background tasks,
    # we might need to rely on unit tests or mock the server.
    
    # However, for this environment, let's try to run a mock test using starlette TestClient if pytest is not available,
    # or just rely on the unit test I will create next.
    pass
