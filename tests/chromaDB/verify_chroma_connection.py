import asyncio
import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.providers.databases.chroma_provider import ChromaProvider

async def verify_chroma_connection():
    print(f"Connecting to ChromaDB at {settings.CHROMA_SERVER_HOST}:{settings.CHROMA_SERVER_PORT}...")
    
    try:
        provider = ChromaProvider()
        print("Successfully initialized ChromaProvider.")
        
        # Create a dummy document
        doc_id = "test_doc_1"
        content = "This is a test document to verify persistence."
        embedding = [0.1] * 1024 # Dummy embedding
        
        print(f"Adding document: {doc_id}")
        await provider.add_documents(
            documents=[{"page_content": content, "metadata": {"source": "test"}, "id": doc_id}],
            embeddings=[embedding]
        )
        
        print("Searching for document...")
        results = await provider.similarity_search(query_embedding=embedding, k=1)
        
        if results and results[0]["page_content"] == content:
            print("SUCCESS: Document retrieved successfully.")
        else:
            print("FAILURE: Document not found or content mismatch.")
            print(f"Results: {results}")
            
    except Exception as e:
        print(f"ERROR: Failed to connect or interact with ChromaDB: {e}")
        print("Ensure the ChromaDB docker container is running: `docker-compose up -d chroma`")

if __name__ == "__main__":
    asyncio.run(verify_chroma_connection())
