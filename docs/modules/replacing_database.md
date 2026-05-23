# Руководство по замене баз данных

## Обзор

Данное руководство описывает процесс замены или добавления новых баз данных в Python AI Service. Система поддерживает три типа баз данных:

1. **Реляционные БД** (PostgreSQL) — для структурированных данных
2. **Графовые БД** (Neo4j) — для графа знаний и связей
3. **Векторные БД** (ChromaDB, Milvus) — для семантического поиска

## Архитектура баз данных

### Компоненты

```
DatabaseFactory (Фабрика)
    ↓
Интерфейсы:
    • IRelationalDatabase
    • IGraphDatabase
    • IVectorStore
    ↓
Провайдеры:
    • PostgresProvider
    • Neo4jProvider
    • ChromaProvider
    • MilvusProvider
    • YourNewProvider ← добавляем здесь
    ↓
Репозитории (DAL):
    • SessionRepository
    • EntryRepository
    • GraphRepository
    • EmbeddingRepository
```

## Замена реляционной БД

### Интерфейс IRelationalDatabase

```python
# app/interfaces/relational_database.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class IRelationalDatabase(ABC):
    """Интерфейс для реляционных баз данных."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Установить соединение с БД."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Закрыть соединение."""
        pass
    
    @abstractmethod
    async def execute(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> None:
        """Выполнить запрос без возврата результата."""
        pass
    
    @abstractmethod
    async def fetch_one(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> Optional[Dict[str, Any]]:
        """Получить одну запись."""
        pass
    
    @abstractmethod
    async def fetch_all(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Получить все записи."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Проверка здоровья БД."""
        pass
```

### Пример: Добавление MySQL

```python
# app/providers/databases/mysql_provider.py

import logging
from typing import List, Dict, Any, Optional
import aiomysql
from app.interfaces.relational_database import IRelationalDatabase

logger = logging.getLogger(__name__)


class MySQLProvider(IRelationalDatabase):
    """Провайдер для MySQL."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация провайдера.
        
        Args:
            config: Конфигурация подключения
        """
        self.config = config
        self.pool = None
        
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 3306)
        self.user = config.get("user", "root")
        self.password = config.get("password", "")
        self.database = config.get("database", "mydb")
        
        self.pool_size = config.get("pool_size", 10)
        self.max_size = config.get("max_size", 20)
    
    async def connect(self) -> None:
        """Создать пул соединений."""
        if self.pool is not None:
            logger.warning("Pool already exists")
            return
        
        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                minsize=self.pool_size,
                maxsize=self.max_size,
                autocommit=True
            )
            
            logger.info(f"Connected to MySQL at {self.host}:{self.port}")
        
        except Exception as e:
            logger.error(f"Failed to connect to MySQL: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Закрыть пул соединений."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
            logger.info("Disconnected from MySQL")
    
    async def execute(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> None:
        """Выполнить запрос."""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params or ())
    
    async def fetch_one(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> Optional[Dict[str, Any]]:
        """Получить одну запись."""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params or ())
                return await cursor.fetchone()
    
    async def fetch_all(
        self,
        query: str,
        params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Получить все записи."""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params or ())
                return await cursor.fetchall()
    
    async def health_check(self) -> bool:
        """Проверка здоровья."""
        try:
            result = await self.fetch_one("SELECT 1 as health")
            return result is not None and result.get("health") == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
```

### Регистрация в фабрике

```python
# app/factory/database_factory.py

from app.providers.databases.mysql_provider import MySQLProvider

class DatabaseFactory:
    _mysql_instance: Optional[MySQLProvider] = None
    _mysql_lock = Lock()
    
    @staticmethod
    def create_relational_database(provider_type: str = "postgres") -> IRelationalDatabase:
        """Создать реляционную БД."""
        from app.core.config import settings
        
        if provider_type == "postgres":
            # ... существующий код ...
            pass
        
        elif provider_type == "mysql":
            if DatabaseFactory._mysql_instance is not None:
                return DatabaseFactory._mysql_instance
            
            with DatabaseFactory._mysql_lock:
                if DatabaseFactory._mysql_instance is not None:
                    return DatabaseFactory._mysql_instance
                
                provider = MySQLProvider(config=settings.DATABASE_CONFIG)
                DatabaseFactory._mysql_instance = provider
                return provider
        
        else:
            raise ValueError(f"Unknown relational database: {provider_type}")
```

## Замена графовой БД

### Интерфейс IGraphDatabase

```python
# app/core/interfaces/i_graph_database.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class IGraphDatabase(ABC):
    """Интерфейс для графовых баз данных."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Установить соединение."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Закрыть соединение."""
        pass
    
    @abstractmethod
    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Выполнить запрос."""
        pass
    
    @abstractmethod
    async def create_node(
        self,
        label: str,
        properties: Dict[str, Any]
    ) -> str:
        """Создать узел."""
        pass
    
    @abstractmethod
    async def create_relationship(
        self,
        from_node_id: str,
        to_node_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """Создать связь."""
        pass
    
    @abstractmethod
    async def find_nodes(
        self,
        label: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Найти узлы."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Проверка здоровья."""
        pass
```

### Пример: Добавление ArangoDB

```python
# app/providers/databases/arango_provider.py

import logging
from typing import List, Dict, Any, Optional
from aioarangodb import ArangoClient
from app.core.interfaces.i_graph_database import IGraphDatabase

logger = logging.getLogger(__name__)


class ArangoProvider(IGraphDatabase):
    """Провайдер для ArangoDB."""
    
    def __init__(self, config: Dict[str, Any]):
        """Инициализация."""
        self.config = config
        
        self.url = config.get("url", "http://localhost:8529")
        self.username = config.get("username", "root")
        self.password = config.get("password", "")
        self.database_name = config.get("database", "_system")
        self.graph_name = config.get("graph", "knowledge_graph")
        
        self.client = None
        self.db = None
        self.graph = None
    
    async def connect(self) -> None:
        """Подключиться к ArangoDB."""
        try:
            self.client = ArangoClient(hosts=self.url)
            
            # Подключение к БД
            self.db = await self.client.db(
                self.database_name,
                username=self.username,
                password=self.password
            )
            
            # Получить или создать граф
            if await self.db.has_graph(self.graph_name):
                self.graph = await self.db.graph(self.graph_name)
            else:
                self.graph = await self.db.create_graph(self.graph_name)
            
            logger.info(f"Connected to ArangoDB at {self.url}")
        
        except Exception as e:
            logger.error(f"Failed to connect to ArangoDB: {e}")
            raise
    
    async def close(self) -> None:
        """Закрыть соединение."""
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("Disconnected from ArangoDB")
    
    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Выполнить AQL запрос."""
        cursor = await self.db.aql.execute(
            query,
            bind_vars=parameters or {}
        )
        return [doc async for doc in cursor]
    
    async def create_node(
        self,
        label: str,
        properties: Dict[str, Any]
    ) -> str:
        """Создать узел (документ)."""
        # Получить или создать коллекцию
        if not await self.db.has_collection(label):
            collection = await self.db.create_collection(label)
        else:
            collection = await self.db.collection(label)
        
        # Вставить документ
        result = await collection.insert(properties)
        return result["_id"]
    
    async def create_relationship(
        self,
        from_node_id: str,
        to_node_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """Создать связь (edge)."""
        # Получить или создать edge collection
        edge_collection_name = f"{relationship_type}_edges"
        
        if not await self.db.has_collection(edge_collection_name):
            edge_collection = await self.db.create_collection(
                edge_collection_name,
                edge=True
            )
        else:
            edge_collection = await self.db.collection(edge_collection_name)
        
        # Создать edge
        edge_data = {
            "_from": from_node_id,
            "_to": to_node_id,
            **(properties or {})
        }
        
        result = await edge_collection.insert(edge_data)
        return result["_id"]
    
    async def find_nodes(
        self,
        label: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Найти узлы."""
        if not await self.db.has_collection(label):
            return []
        
        collection = await self.db.collection(label)
        
        if properties:
            # Поиск с фильтром
            query = f"""
            FOR doc IN {label}
            FILTER {' AND '.join(f'doc.{k} == @{k}' for k in properties.keys())}
            RETURN doc
            """
            return await self.execute_query(query, properties)
        else:
            # Все документы
            cursor = await collection.all()
            return [doc async for doc in cursor]
    
    async def health_check(self) -> bool:
        """Проверка здоровья."""
        try:
            version = await self.db.version()
            return version is not None
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
```

## Замена векторной БД

### Интерфейс IVectorStore

```python
# app/interfaces/vector_store.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class IVectorStore(ABC):
    """Интерфейс для векторных баз данных."""
    
    @abstractmethod
    async def add_documents(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Добавить документы."""
        pass
    
    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Поиск похожих документов."""
        pass
    
    @abstractmethod
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> int:
        """Удалить документы."""
        pass
    
    @abstractmethod
    async def get_by_ids(
        self,
        ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Получить документы по ID."""
        pass
    
    @abstractmethod
    async def reset(self) -> None:
        """Очистить коллекцию."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Проверка здоровья."""
        pass
```

### Пример реализации см. в документе

См. подробный пример реализации Milvus в:
- [VECTOR_STORE_MIGRATION_GUIDE.md](../VECTOR_STORE_MIGRATION_GUIDE.md)
- [app/providers/databases/milvus_provider.py](../../app/providers/databases/milvus_provider.py)

### Пример: Добавление Qdrant

```python
# app/providers/databases/qdrant_provider.py

import logging
from typing import List, Dict, Any, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.interfaces.vector_store import IVectorStore

logger = logging.getLogger(__name__)


class QdrantProvider(IVectorStore):
    """Провайдер для Qdrant."""
    
    def __init__(self, config: Dict[str, Any]):
        """Инициализация."""
        self.config = config
        
        self.host = config.get("qdrant_host", "localhost")
        self.port = config.get("qdrant_port", 6333)
        self.collection_name = config.get("qdrant_collection", "documents")
        self.vector_size = config.get("embedding_dimension", 1024)
        
        self.client = None
    
    async def _ensure_client(self):
        """Ленивая инициализация клиента."""
        if self.client is None:
            self.client = AsyncQdrantClient(
                host=self.host,
                port=self.port
            )
            
            # Создать коллекцию если не существует
            collections = await self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.collection_name}")
    
    async def add_documents(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadata: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Добавить документы."""
        await self._ensure_client()
        
        # Генерация ID если не предоставлены
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in documents]
        
        # Подготовка точек
        points = []
        for i, (doc_id, doc, emb) in enumerate(zip(ids, documents, embeddings)):
            payload = {
                "text": doc,
                **(metadata[i] if metadata else {})
            }
            
            points.append(PointStruct(
                id=doc_id,
                vector=emb,
                payload=payload
            ))
        
        # Вставка
        await self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        logger.info(f"Added {len(points)} documents to Qdrant")
        return ids
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Поиск похожих документов."""
        await self._ensure_client()
        
        # Построение фильтра
        query_filter = None
        if filter_dict:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            
            query_filter = Filter(must=conditions)
        
        # Поиск
        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=query_filter
        )
        
        # Форматирование результатов
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "text": result.payload.get("text", ""),
                "metadata": {
                    k: v for k, v in result.payload.items()
                    if k != "text"
                }
            })
        
        return formatted_results
    
    async def delete(
        self,
        ids: Optional[List[str]] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> int:
        """Удалить документы."""
        await self._ensure_client()
        
        if ids:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=ids
            )
            return len(ids)
        
        elif filter_dict:
            # Удаление по фильтру
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            
            query_filter = Filter(must=conditions)
            
            result = await self.client.delete(
                collection_name=self.collection_name,
                points_selector=query_filter
            )
            
            return result.operation_id
        
        return 0
    
    async def get_by_ids(
        self,
        ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Получить документы по ID."""
        await self._ensure_client()
        
        results = await self.client.retrieve(
            collection_name=self.collection_name,
            ids=ids
        )
        
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "text": result.payload.get("text", ""),
                "metadata": {
                    k: v for k, v in result.payload.items()
                    if k != "text"
                }
            })
        
        return formatted_results
    
    async def reset(self) -> None:
        """Очистить коллекцию."""
        await self._ensure_client()
        
        await self.client.delete_collection(self.collection_name)
        
        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE
            )
        )
        
        logger.info(f"Reset collection: {self.collection_name}")
    
    async def health_check(self) -> bool:
        """Проверка здоровья."""
        try:
            await self._ensure_client()
            collections = await self.client.get_collections()
            return collections is not None
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
```

## Конфигурация

### Добавление в config.py

```python
# app/core/config.py

class Settings(BaseSettings):
    # MySQL Configuration
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "mydb"
    
    # ArangoDB Configuration
    ARANGO_URL: str = "http://localhost:8529"
    ARANGO_USERNAME: str = "root"
    ARANGO_PASSWORD: str = ""
    ARANGO_DATABASE: str = "_system"
    ARANGO_GRAPH: str = "knowledge_graph"
    
    # Qdrant Configuration
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "documents"
    
    # Database Type Selection
    RELATIONAL_DB_TYPE: str = "postgres"  # postgres, mysql
    GRAPH_DB_TYPE: str = "neo4j"  # neo4j, arango
    VECTOR_STORE_TYPE: str = "chroma"  # chroma, milvus, qdrant
```

### Добавление в .env

```bash
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DB=mydb

# ArangoDB
ARANGO_URL=http://localhost:8529
ARANGO_USERNAME=root
ARANGO_PASSWORD=your-password
ARANGO_DATABASE=_system
ARANGO_GRAPH=knowledge_graph

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=documents

# Selection
RELATIONAL_DB_TYPE=postgres
GRAPH_DB_TYPE=neo4j
VECTOR_STORE_TYPE=chroma
```

## Миграция данных

### Скрипт миграции

```python
# scripts/migrate_database.py

import asyncio
from app.factory.database_factory import DatabaseFactory


async def migrate_vector_store(from_type: str, to_type: str):
    """Миграция векторной БД."""
    print(f"Migrating from {from_type} to {to_type}...")
    
    # 1. Подключиться к старой БД
    old_store = DatabaseFactory.create_vector_store(from_type)
    
    # 2. Получить все документы
    # (Реализация зависит от провайдера)
    documents = await old_store.get_all_documents()
    
    # 3. Подключиться к новой БД
    new_store = DatabaseFactory.create_vector_store(to_type)
    
    # 4. Вставить документы
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        
        await new_store.add_documents(
            documents=[d["text"] for d in batch],
            embeddings=[d["embedding"] for d in batch],
            metadata=[d["metadata"] for d in batch],
            ids=[d["id"] for d in batch]
        )
        
        print(f"Migrated {i+len(batch)}/{len(documents)} documents")
    
    print("Migration completed!")


if __name__ == "__main__":
    asyncio.run(migrate_vector_store("chroma", "milvus"))
```

## Тестирование

### Тест провайдера

```python
# tests/providers/test_your_database.py

import pytest
from app.providers.databases.your_provider import YourProvider


@pytest.fixture
async def provider():
    """Фикстура провайдера."""
    config = {
        "host": "localhost",
        "port": 1234,
        # ... другие параметры
    }
    
    provider = YourProvider(config)
    await provider.connect()
    
    yield provider
    
    await provider.close()


@pytest.mark.asyncio
async def test_health_check(provider):
    """Тест health check."""
    is_healthy = await provider.health_check()
    assert is_healthy is True


@pytest.mark.asyncio
async def test_add_and_search(provider):
    """Тест добавления и поиска."""
    # Добавить документы
    ids = await provider.add_documents(
        documents=["test doc 1", "test doc 2"],
        embeddings=[[0.1] * 1024, [0.2] * 1024]
    )
    
    assert len(ids) == 2
    
    # Поиск
    results = await provider.search(
        query_embedding=[0.1] * 1024,
        top_k=1
    )
    
    assert len(results) > 0
    assert "test doc 1" in results[0]["text"]
```

## Лучшие практики

### 1. Connection Pooling

```python
class PooledProvider:
    def __init__(self, config):
        self.pool = None
        self.pool_size = config.get("pool_size", 10)
    
    async def connect(self):
        self.pool = await create_pool(
            minsize=self.pool_size,
            maxsize=self.pool_size * 2
        )
```

### 2. Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class RobustProvider:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def execute_query(self, query: str):
        return await self._execute_impl(query)
```

### 3. Health Monitoring

```python
class MonitoredProvider:
    async def health_check(self) -> bool:
        try:
            start = time.time()
            result = await self._check_health()
            latency = time.time() - start
            
            logger.info(f"Health check: {result}, latency: {latency:.2f}s")
            return result
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
```

## Troubleshooting

### Проблема: Соединение не устанавливается

**Решение**:
1. Проверьте host и port в конфигурации
2. Убедитесь что БД запущена
3. Проверьте firewall правила
4. Проверьте credentials

### Проблема: Медленные запросы

**Решение**:
1. Добавьте индексы
2. Увеличьте размер пула соединений
3. Используйте батчинг для массовых операций
4. Оптимизируйте запросы

### Проблема: Утечки памяти

**Решение**:
1. Всегда закрывайте соединения
2. Используйте context managers
3. Ограничьте размер результатов
4. Мониторьте использование памяти

## Ссылки

- [Architecture](../architecture.md)
- [Configuration](../configuration.md)
- [Database Factory Code](../../app/factory/database_factory.py)
- [Vector Store Migration Guide](../VECTOR_STORE_MIGRATION_GUIDE.md)
- [Existing Providers](../../app/providers/databases/)
