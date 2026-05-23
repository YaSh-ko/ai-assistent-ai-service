#!/usr/bin/env python3
"""
Test the current model configured in app/core/config.py
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# IMPORTANT: Clear GIGACHAT_CREDENTIALS to force using CLIENT_ID/SECRET
# This fixes the "Can't decode 'Authorization' header" error
os.environ.pop('GIGACHAT_CREDENTIALS', None)

from app.factory.model_factory import ModelFactory
from app.core.config import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reload settings after clearing env var
settings = Settings()


async def test_current_model(prompt: str = "Привет! Как дела?"):
    """Test the current model with a simple query."""
    
    current_model = settings.CURRENT_MODEL
    
    print("="*60)
    print(f"Testing Current Model: {current_model}")
    print("="*60)
    print()
    
    try:
        # Get the model provider
        provider = ModelFactory.get_model(current_model)
        print(f"✓ Provider loaded: {provider.name}")
        print()
        
        # Check availability
        print("Checking model availability...")
        is_available = await provider.is_available()
        
        if not is_available:
            print("✗ Model is NOT available")
            print("  Check your credentials in .env file:")
            print(f"    GIGACHAT_CLIENT_ID: {settings.GIGACHAT_CLIENT_ID[:20]}...")
            print(f"    GIGACHAT_CLIENT_SECRET: {'*' * 20}")
            return False
        
        print("✓ Model is available")
        print()
        
        # Send test query
        print(f"Sending query: '{prompt}'")
        print()
        
        response = await provider.generate(prompt=prompt)
        
        print("Response:")
        print("-" * 60)
        print(response.content)
        print("-" * 60)
        print()
        
        print("✓ Test successful!")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        await ModelFactory.close_all()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test current model from config")
    parser.add_argument("--prompt", "-p", 
                       default="Привет! Как дела?",
                       help="Test prompt to send to the model")
    
    args = parser.parse_args()
    
    print()
    print("Configuration:")
    print(f"  Current Model: {settings.CURRENT_MODEL}")
    print(f"  GigaChat Scope: {settings.GIGACHAT_SCOPE}")
    print("  Using CLIENT_ID/SECRET (not GIGACHAT_CREDENTIALS)")
    print()
    
    success = await test_current_model(args.prompt)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
