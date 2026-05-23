# Vector Store Migration Guide

## Overview

This guide explains how to switch between different vector store implementations (Chroma and Milvus) in the Python AI Service.

## Supported Vector Stores

### 1. ChromaDB (Default)
- **Type**: Embedded/Server vector database
- **Best for**: Development, small to medium datasets
- **Pros**: Easy setup, good for prototyping
- **Cons**: Limited scalability for very large datasets

### 2. Milvus
- **Type**: Distributed vector database
- **Best for**: Production, large-scale deployments
- **Pros**: High performance, scalability, advanced features
- **Cons**: Requires separate server, more complex setup

## Architecture

### IVectorStore Interface

All vector stores implement the `IVectorStore` interface:

```python
class IVectorStore(ABC):
    async def add_documents(documents, embeddings) -> None
    async def similarity_search(query_embedding, k, filter) -> List[Dict]
    async def reset() -> None
    async def delete_documents(ids) -> None
    async def get_by_filter(filter) -> List[Dict]
```

### Implementation Files

- **Interface**: `app/interfaces/vector_store.py`
- **Chroma**: `app/providers/databases/chroma_provider.py`
- **Milvus**: `app/providers/databases/milvus_provider.py`
- **Factory**: `app/factory/database_factory.py`

## Quick Start: Switching Vector Stores

### Using the Switch Script

```bash
# Show current configuration
python3 scripts/switch_vector_store.py show

# Switch to Milvus
python3 scripts/switch_vector_store.py milvus

# Switch to Chroma
python3 scripts/switch_vector_store.py chroma
```

### Manual Configuration

Edit `.env` file:

```bash
# For Chroma (default)
VECTOR_STORE_TYPE=chroma

# For Milvus
VECTOR_STORE_TYPE=milvus
```

## Setting Up Milvus

### Option 1: Docker (Recommended)

```bash
# Start Milvus standalone
docker run -d \
  --name milvus \
  -p 19530:19530 \
  -p 9091:9091 \
  milvusdb/milvus:latest

# Verify Milvus is running
docker ps | grep milvus
```

### Option 2: Docker Compose

Create `docker-compose-milvus.yml`:

```yaml
version: '3.5'

services:
  milvus:
    image: milvusdb/milvus:latest
    container_name: milvus
    ports:
      - "19530:19530"
      - "9091:9091"
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    volumes:
      - milvus_data:/var/lib/milvus
    depends_on:
      - etcd
      - minio

  etcd:
    image: quay.io/coreos/etcd:latest
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
    volumes:
      - etcd_data:/etcd

  minio:
    image: minio/minio:latest
    environment:
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    volumes:
      - minio_data:/minio_data
    command: minio server /minio_data

volumes:
  milvus_data:
  etcd_data:
  minio_data:
```

Start with:
```bash
docker-compose -f docker-compose-milvus.yml up -d
```

### Install Python Client

```bash
pip install pymilvus
```

### Configure Milvus in .env

```bash
# Milvus Configuration
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=
MILVUS_PASSWORD=
MILVUS_COLLECTION=chat_history
```

## Testing

### Test Milvus Connection

```bash
python3 scripts/test_milvus_vector_store.py
```

Expected output:
```
============================================================
Testing Milvus Vector Store
============================================================

Configuration:
  Host: localhost
  Port: 19530
  Collection: chat_history
  Embedding Dimension: 1024

1. Initializing Milvus provider...
✓ Milvus provider initialized

2. Testing add_documents...
✓ Added 3 documents

3. Testing similarity_search...
✓ Found 2 similar documents:
  1. ID: doc1
     Content: Machine learning is a subset of artificial intel...
     Score: 0.9876
     Metadata: {'source': 'test', 'category': 'AI'}

...

✓ All tests passed!
```

### Test with RAG

```python
from app.factory.database_factory import DatabaseFactory
from app.chains.rag_chain import RAGChain

# Create vector store (uses configured type)
vector_store = DatabaseFactory.create_vector_store()

# Use in RAG chain
rag_chain = RAGChain(vector_store=vector_store, ...)
```

## Migration Process

### 1. Backup Current Data

```bash
# For Chroma
# Backup the collection data
python3 scripts/backup_chroma.py

# For Milvus
# Export collection
python3 scripts/backup_milvus.py
```

### 2. Switch Vector Store

```bash
python3 scripts/switch_vector_store.py milvus
```

### 3. Migrate Data (Optional)

If you need to migrate existing embeddings:

```python
from app.providers.databases.chroma_provider import ChromaProvider
from app.providers.databases.milvus_provider import MilvusProvider

async def migrate_data():
    # Source
    chroma = ChromaProvider()
    
    # Destination
    milvus = MilvusProvider()
    
    # Get all documents from Chroma
    docs = await chroma.get_by_filter({})
    
    # Extract embeddings (you'll need to retrieve these)
    # embeddings = ...
    
    # Add to Milvus
    await milvus.add_documents(docs, embeddings)
    
    print(f"Migrated {len(docs)} documents")
```

### 4. Restart Application

```bash
# Restart your service
systemctl restart python-ai-service

# Or if running manually
python3 -m uvicorn app.main:app --reload
```

### 5. Verify

```bash
# Test the new vector store
python3 scripts/test_vector_store.py

# Test RAG functionality
curl -X POST http://localhost:8001/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Test query"}'
```

## Performance Comparison

### Chroma
- **Insert Speed**: ~1000 docs/sec
- **Search Speed**: ~100 queries/sec
- **Memory Usage**: Moderate
- **Scalability**: Up to millions of vectors

### Milvus
- **Insert Speed**: ~10,000 docs/sec
- **Search Speed**: ~1000 queries/sec
- **Memory Usage**: Configurable
- **Scalability**: Billions of vectors

## Configuration Reference

### Chroma Settings

```bash
CHROMA_SERVER_HOST=api.delez-repo.ru
CHROMA_SERVER_PORT=8001
CHROMA_SERVER_SSL=False
CHROMA_DB_PATH=./chroma_db
```

### Milvus Settings

```bash
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=
MILVUS_PASSWORD=
MILVUS_COLLECTION=chat_history
```

### Common Settings

```bash
# Vector store selection
VECTOR_STORE_TYPE=milvus  # or "chroma"

# Embedding configuration
EMBEDDING_MODEL=EmbeddingsGigaR
EMBEDDING_DIMENSION=1024

# Search configuration
DISTANCE_METRIC=cosine  # or "l2", "ip"
TOP_K_RESULTS=5
SIMILARITY_THRESHOLD=0.7
```

## Troubleshooting

### Milvus Connection Failed

**Error**: `Failed to connect to Milvus`

**Solutions**:
1. Check if Milvus is running:
   ```bash
   docker ps | grep milvus
   ```

2. Verify port is accessible:
   ```bash
   telnet localhost 19530
   ```

3. Check Milvus logs:
   ```bash
   docker logs milvus
   ```

### pymilvus Not Installed

**Error**: `ModuleNotFoundError: No module named 'pymilvus'`

**Solution**:
```bash
pip install pymilvus
```

### Collection Already Exists

**Error**: `Collection 'chat_history' already exists`

**Solution**:
```python
# Reset the collection
await provider.reset()
```

### Dimension Mismatch

**Error**: `Dimension mismatch: expected 1024, got 768`

**Solution**: Ensure `EMBEDDING_DIMENSION` in `.env` matches your embedding model:
```bash
EMBEDDING_DIMENSION=1024  # For GigaChat
```

## Best Practices

### 1. Development vs Production

- **Development**: Use Chroma for simplicity
- **Production**: Use Milvus for performance and scalability

### 2. Index Configuration

For Milvus, choose appropriate index type:

```python
# For small datasets (< 1M vectors)
index_params = {
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 128}
}

# For large datasets (> 1M vectors)
index_params = {
    "metric_type": "COSINE",
    "index_type": "IVF_SQ8",
    "params": {"nlist": 1024}
}
```

### 3. Connection Pooling

Reuse vector store instances:

```python
# Good - singleton pattern
vector_store = DatabaseFactory.create_vector_store()

# Bad - creates new connection each time
vector_store = MilvusProvider()
```

### 4. Batch Operations

Insert documents in batches for better performance:

```python
# Good - batch insert
await provider.add_documents(docs_batch, embeddings_batch)

# Bad - one at a time
for doc, emb in zip(docs, embeddings):
    await provider.add_documents([doc], [emb])
```

## Adding New Vector Stores

To add a new vector store (e.g., Pinecone, Weaviate):

1. Create provider class implementing `IVectorStore`:
   ```python
   # app/providers/databases/pinecone_provider.py
   class PineconeProvider(IVectorStore):
       async def add_documents(...): ...
       async def similarity_search(...): ...
       # ... implement all methods
   ```

2. Update `DatabaseFactory`:
   ```python
   elif provider_type == "pinecone":
       return PineconeProvider(config=settings.DATABASE_CONFIG)
   ```

3. Add configuration to `config.py`:
   ```python
   PINECONE_API_KEY: str = ""
   PINECONE_ENVIRONMENT: str = ""
   ```

4. Update `.env`:
   ```bash
   VECTOR_STORE_TYPE=pinecone
   PINECONE_API_KEY=your-key
   ```

## References

- [Milvus Documentation](https://milvus.io/docs)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Vector Database Comparison](https://milvus.io/docs/comparison.md)
