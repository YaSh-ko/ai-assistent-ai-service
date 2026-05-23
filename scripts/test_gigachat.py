
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

import os
# Clear environment variable to force using .env value via Settings
os.environ.pop('GIGACHAT_CREDENTIALS', None)

from app.factory.model_factory import ModelFactory
from app.core.config import Settings

# Create fresh settings after clearing env
settings = Settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_gigachat(version="gigachat"):
    print(f"\n--- Testing GigaChat: {version} ---")
    try:
        provider = ModelFactory.get_model(version)
        print(f"Provider: {provider.name}")
        
        # Test availability (token check)
        print("Checking availability...")
        is_avail = await provider.is_available()
        print(f"Is available: {is_avail}")
        
        if not is_avail:
            print("Model reported as NOT available. Skipping prompt test.")
            return False
            
        print("Sending prompt: 'Привет, как тебя зовут?'")
        response = await provider.generate(prompt="Привет, как тебя зовут?")
        print(f"Response: {response.content}")
        return True
    except Exception as e:
        print(f"Error testing {version}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("Testing GigaChat settings...")
    print(f"GIGACHAT_CREDENTIALS present: {bool(settings.GIGACHAT_CREDENTIALS)}")
    print(f"GIGACHAT_CREDENTIALS length: {len(settings.GIGACHAT_CREDENTIALS)}")
    print(f"GIGACHAT_CLIENT_ID: {settings.GIGACHAT_CLIENT_ID}")
    print(f"GIGACHAT_SCOPE: {settings.GIGACHAT_SCOPE}")

    # Test Base
    await test_gigachat("gigachat")
    
    # Test Pro
    await test_gigachat("gigachat_pro")
    
    # Test Max
    await test_gigachat("gigachat_max")
    
    # Close all providers
    await ModelFactory.close_all()

if __name__ == "__main__":
    asyncio.run(main())
