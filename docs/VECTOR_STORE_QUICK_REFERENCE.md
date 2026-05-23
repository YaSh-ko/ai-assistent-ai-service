# Vector Store Quick Reference

## Quick Commands

### Show Current Configuration
```bash
python3 scripts/switch_vector_store.py show
```

### Switch to Milvus
```bash
python3 scripts/switch_vector_store.py milvus
```

### Switch to Chroma
```bash
python3 scripts/switch_vector_store.py chroma
```

### Test Milvus
```bash
python3 scripts/test_milvus_vector_store.py
```

## Setup Milvus (Docker)

```bash
# Start Milvus
docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest

# Install Python client
pip install pymilvus

# Verify
docker ps | grep milvus
```

## Configuration (.env)

```bash
# Vector Store Selection
VECTOR_STORE_TYPE=chroma  # or "milvus"

# Chroma Settings
CHROMA_SERVER_HOST=api.delez-repo.ru
CHROMA_SERVER_PORT=8001
CHROMA_SERVER_SSL=False

# Milvus Settings
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=
MILVUS_PASSWORD=
MILVUS_COLLECTION=chat_history
```

## Code Usage

### Get Vector Store (Auto-configured)
```python
from app.factory.database_factory import DatabaseFactory

# Uses VECTOR_STORE_TYPE from config
vector_store = DatabaseFactory.create_vector_store()
```

### Explicit Type
```python
# Force specific type
chroma = DatabaseFactory.create_vector_store("chroma")
milvus = DatabaseFactory.create_vector_store("milvus")
```

### Add Documents
```python
documents = [
    {
        "id": "doc1",
        "page_content": "Content here",
        "metadata": {"source": "test"}
    }
]
embeddings = [[0.1] * 1024]  # From embedding model

await vector_store.add_documents(documents, embeddings)
```

### Search
```python
query_embedding = [0.15] * 1024  # From embedding model
results = await vector_store.similarity_search(
    query_embedding,
    k=5,
    filter={"source": "test"}
)
```

### Delete
```python
await vector_store.delete_documents(["doc1", "doc2"])
```

### Reset
```python
await vector_store.reset()  # Clears all data
```

## Troubleshooting

### Milvus Not Running
```bash
docker start milvus
# or
docker run -d --name milvus -p 19530:19530 milvusdb/milvus:latest
```

### pymilvus Not Installed
```bash
pip install pymilvus
```

### Connection Error
```bash
# Check if port is accessible
telnet localhost 19530

# Check Milvus logs
docker logs milvus
```

### Wrong Vector Store Type
```bash
# Check current config
python3 scripts/switch_vector_store.py show

# Switch if needed
python3 scripts/switch_vector_store.py milvus
```

## Performance Tips

### Batch Inserts
```python
# Good - batch
await vector_store.add_documents(docs, embeddings)

# Bad - one by one
for doc, emb in zip(docs, embeddings):
    await vector_store.add_documents([doc], [emb])
```

### Reuse Connections
```python
# Good - singleton
store = DatabaseFactory.create_vector_store()

# Bad - new connection each time
store = MilvusProvider()
```

### Choose Right Store
- **Development**: Chroma (easier setup)
- **Production**: Milvus (better performance)
- **Small datasets** (< 1M vectors): Either
- **Large datasets** (> 1M vectors): Milvus

## When to Use Which

### Use Chroma When:
- ✅ Prototyping/Development
- ✅ Small to medium datasets
- ✅ Simple setup required
- ✅ Embedded database preferred

### Use Milvus When:
- ✅ Production deployment
- ✅ Large-scale datasets (millions+ vectors)
- ✅ High performance required
- ✅ Advanced features needed (partitioning, GPU)

## Common Patterns

### RAG Chain Integration
```python
from app.chains.rag_chain import RAGChain
from app.factory.database_factory import DatabaseFactory

vector_store = DatabaseFactory.create_vector_store()
rag_chain = RAGChain(vector_store=vector_store, ...)
```

### Search Service Integration
```python
from app.providers.search.vector_search_provider import VectorSearchProvider
from app.factory.database_factory import DatabaseFactory

vector_store = DatabaseFactory.create_vector_store()
search_provider = VectorSearchProvider(vector_store)
```

## Migration Checklist

- [ ] Backup current data
- [ ] Install new vector store (if Milvus)
- [ ] Install Python client (`pip install pymilvus`)
- [ ] Update `.env` (`VECTOR_STORE_TYPE=milvus`)
- [ ] Test connection (`python3 scripts/test_milvus_vector_store.py`)
- [ ] Migrate data (if needed)
- [ ] Restart application
- [ ] Verify functionality

## Documentation

- **Full Guide**: [VECTOR_STORE_MIGRATION_GUIDE.md](./VECTOR_STORE_MIGRATION_GUIDE.md)
- **Implementation**: [MILVUS_IMPLEMENTATION_SUMMARY.md](./MILVUS_IMPLEMENTATION_SUMMARY.md)
- **Milvus Docs**: https://milvus.io/docs
- **Chroma Docs**: https://docs.trychroma.com/
