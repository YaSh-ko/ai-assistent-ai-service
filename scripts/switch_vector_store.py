#!/usr/bin/env python3
"""
Script to switch between vector store implementations (Chroma <-> Milvus).
Updates the .env file with the selected vector store type.
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))


def update_env_file(vector_store_type: str):
    """Update VECTOR_STORE_TYPE in .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    
    if not env_path.exists():
        print(f"✗ .env file not found at {env_path}")
        return False
    
    # Read current .env content
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Update VECTOR_STORE_TYPE line
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('VECTOR_STORE_TYPE='):
            lines[i] = f'VECTOR_STORE_TYPE={vector_store_type}\n'
            updated = True
            break
    
    # If not found, add it
    if not updated:
        lines.append(f'\nVECTOR_STORE_TYPE={vector_store_type}\n')
    
    # Write back
    with open(env_path, 'w') as f:
        f.writelines(lines)
    
    print(f"✓ Updated .env: VECTOR_STORE_TYPE={vector_store_type}")
    return True


def show_current_config():
    """Show current vector store configuration."""
    try:
        from app.core.config import settings
        
        print("\nCurrent Configuration:")
        print("=" * 60)
        print(f"Vector Store Type: {settings.VECTOR_STORE_TYPE}")
        print()
        
        if settings.VECTOR_STORE_TYPE == "chroma":
            print("Chroma Settings:")
            print(f"  Host: {settings.CHROMA_SERVER_HOST}")
            print(f"  Port: {settings.CHROMA_SERVER_PORT}")
            print(f"  SSL: {settings.CHROMA_SERVER_SSL}")
        elif settings.VECTOR_STORE_TYPE == "milvus":
            print("Milvus Settings:")
            print(f"  Host: {settings.MILVUS_HOST}")
            print(f"  Port: {settings.MILVUS_PORT}")
            print(f"  Collection: {settings.MILVUS_COLLECTION}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ Error loading config: {e}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Switch between vector store implementations"
    )
    parser.add_argument(
        "store_type",
        nargs='?',
        choices=["chroma", "milvus", "show"],
        help="Vector store type to switch to, or 'show' to display current config"
    )
    
    args = parser.parse_args()
    
    print()
    print("Vector Store Switcher")
    print("=" * 60)
    
    if not args.store_type or args.store_type == "show":
        show_current_config()
        print("\nUsage:")
        print("  python3 scripts/switch_vector_store.py chroma   # Switch to Chroma")
        print("  python3 scripts/switch_vector_store.py milvus   # Switch to Milvus")
        print("  python3 scripts/switch_vector_store.py show     # Show current config")
        return 0
    
    # Update .env file
    if update_env_file(args.store_type):
        print()
        print(f"✓ Switched to {args.store_type.upper()}")
        print()
        print("Next steps:")
        
        if args.store_type == "milvus":
            print("  1. Ensure Milvus server is running:")
            print("     docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest")
            print("  2. Install pymilvus:")
            print("     pip install pymilvus")
            print("  3. Test the connection:")
            print("     python3 scripts/test_milvus_vector_store.py")
        else:
            print("  1. Ensure ChromaDB server is running")
            print("  2. Test the connection:")
            print("     python3 tests/chromaDB/verify_chroma_connection.py")
        
        print("  4. Restart your application to use the new vector store")
        print()
        
        # Show new config
        show_current_config()
        
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
