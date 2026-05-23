#!/usr/bin/env python3
"""
Quick stress test - simplified version for testing.
"""

import asyncio
import httpx
import time


async def test_service():
    """Quick test of the service."""
    import os
    base_url = os.getenv("BASE_URL", "http://localhost:8001")  # Default to 8001
    
    print(f"Testing service at {base_url}...")
    print("(To use different port: BASE_URL=http://localhost:PORT python3 scripts/quick_test.py)")
    print()
    
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        # Test health endpoint
        try:
            response = await client.get("/health")
            print(f"✓ Health check: {response.status_code}")
            if response.status_code == 200:
                try:
                    print(f"  Response: {response.json()}")
                except Exception:
                    print(f"  Response (text): {response.text[:100]}")
            else:
                print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"✗ Health check failed: {e}")
            print(f"\nPlease start the service on port {base_url.split(':')[-1]}:")
            print(f"  python3 -m uvicorn app.main:app --host 0.0.0.0 --port {base_url.split(':')[-1]}")
            print("\nOr set BASE_URL environment variable:")
            print("  BASE_URL=http://localhost:YOUR_PORT python3 scripts/quick_test.py")
            return False
        
        # Test session creation
        try:
            response = await client.post(
                "/api/v1/chat/sessions",
                json={"user_id": "test_user"}
            )
            print(f"✓ Session creation: {response.status_code}")
            if response.status_code == 200:
                session_data = response.json()
                print(f"  Session ID: {session_data.get('session_id')}")
                session_id = session_data['session_id']
            else:
                print(f"  Response: {response.text}")
                return False
        except Exception as e:
            print(f"✗ Session creation failed: {e}")
            return False
        
        # Test simple message
        try:
            start_time = time.time()
            response = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                json={"content": "Привет!"}
            )
            latency = (time.time() - start_time) * 1000
            print(f"✓ Message send: {response.status_code}")
            print(f"  Latency: {latency:.2f}ms")
            if response.status_code == 200:
                data = response.json()
                print(f"  Response length: {len(data.get('assistant_response', ''))}")
            else:
                print(f"  Response: {response.text}")
        except Exception as e:
            print(f"✗ Message send failed: {e}")
            return False
        
        # Cleanup
        try:
            await client.post(f"/api/v1/chat/sessions/{session_id}/close")
            print("✓ Session closed")
        except Exception:
            pass
    
    print("\n✓ All tests passed!")
    return True


async def main():
    """Main entry point."""
    print("="*60)
    print("Quick Service Test")
    print("="*60)
    print()
    
    success = await test_service()
    
    if success:
        print("\nService is ready for stress testing!")
        print("\nRun stress tests:")
        print("  python scripts/stress_test.py --users 10 --duration 30 --rps 10 --type simple")
    else:
        print("\nService is not ready. Please fix the issues above.")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
