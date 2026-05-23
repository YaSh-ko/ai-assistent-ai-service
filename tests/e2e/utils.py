import json
import asyncio
import httpx
import logging
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.factory.database_factory import DatabaseFactory
from app.providers.databases.postgres_provider import PostgresProvider
from app.providers.databases.chroma_provider import ChromaProvider
from app.providers.databases.neo4j_provider import Neo4jProvider

logger = logging.getLogger(__name__)

async def create_test_session(client, user_id: str) -> str:
    """Create a new test session via API."""
    response = await client.post("/api/v1/chat/sessions", json={"user_id": user_id})
    response.raise_for_status()
    return response.json()["session_id"]

async def seed_test_data(user_id: str, diary_entries: List[Dict], graph_data: Optional[Dict] = None):
    """
    Seed test data into PostgreSQL, ChromaDB, and Neo4j.
    diary_entries: List of {title, description, timestamp, embedding}
    graph_data: {nodes: [], relationships: []}
    """
    from datetime import datetime
    
    # 1. Seed PostgreSQL
    postgres = DatabaseFactory.create_relational_database()
    await postgres.connect()
    try:
        # Ensure user exists for FK constraint
        await postgres.execute("""
            INSERT INTO "user" (id, name, email, "emailVerified", "createdAt", "updatedAt")
            VALUES ($1, 'Test User E2E', 'e2e@example.com', false, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """, {"id": user_id})
        
        for entry in diary_entries:
            ts = entry["timestamp"]
            if isinstance(ts, str):
                # Clean up Z and convert to datetime
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                
            await postgres.execute("""
                INSERT INTO entries (id, user_id, title, description, event_date, created_at, updated_at)
                VALUES (gen_random_uuid(), $1, $2, $3, $4, NOW(), NOW())
            """, {
                "user_id": user_id, 
                "title": entry["title"], 
                "description": entry["description"], 
                "timestamp": ts
            })
            
        # 2. Seed ChromaDB
        chroma = DatabaseFactory.create_vector_store()
        documents = [
            {
                "page_content": f"{e['title']}\n{e['description']}",
                "metadata": {"user_id": user_id, "timestamp": e["timestamp"]}
            } for e in diary_entries
        ]
        # Pad embeddings to 1024 if they are shorter
        embeddings = []
        for e in diary_entries:
            emb = e["embedding"]
            if len(emb) < 1024:
                emb = emb + [0.0] * (1024 - len(emb))
            embeddings.append(emb)
            
        await chroma.add_documents(documents, embeddings)
        
        # 3. Seed Neo4j (if provided) — skip gracefully if Neo4j is unavailable in CI
        if graph_data:
            try:
                neo4j = await DatabaseFactory.create_graph_database()
                # Basic implementation for seeding nodes/rels
                for node in graph_data.get("nodes", []):
                    query = f"MERGE (n:{node['label']} {{id: $id}}) SET n += $props"
                    await neo4j.execute_write(query, {"id": node["id"], "props": node.get("properties", {})})
                
                for rel in graph_data.get("relationships", []):
                    query = (
                        f"MATCH (a {{id: $start_id}}), (b {{id: $end_id}}) "
                        f"MERGE (a)-[r:{rel['type']}]->(b) SET r += $props"
                    )
                    await neo4j.execute_write(query, {"start_id": rel["start_id"], "end_id": rel["end_id"], "props": rel.get("properties", {})})
            except Exception as e:
                logger.warning(f"Neo4j seeding skipped (unavailable in CI): {e}")
    finally:
        # We don't disconnect postgres here because it might be a singleton 
        # used by others, but we ensured it's connected.
        pass

async def cleanup_test_data(user_id: str):
    """Wipe test data for a specific user."""
    # 1. Cleanup PostgreSQL
    postgres = DatabaseFactory.create_relational_database()
    await postgres.connect()
    await postgres.execute("DELETE FROM chat_sessions WHERE user_id = $1", {"user_id": user_id})
    await postgres.execute("DELETE FROM entries WHERE user_id = $1", {"user_id": user_id})
    
    # 2. Cleanup ChromaDB
    try:
        chroma = DatabaseFactory.create_vector_store()
        # Chroma doesn't have a direct "delete by filter" in IVectorStore yet, 
        # but we can use reset() for complete wipe or add a method.
        # For E2E, reset() is safer but destructive. 
        # Let's assume we use a specific test collection or reset.
        await chroma.reset()
    except Exception:
        pass
    
    # 3. Cleanup Neo4j
    try:
        neo4j = await DatabaseFactory.create_graph_database()
        await neo4j.execute_write("MATCH (n) DETACH DELETE n", {})
    except Exception:
        pass

async def wait_for_streaming(response_stream) -> str:
    """Aggregate content from an SSE stream."""
    full_content = ""
    async for line in response_stream.aiter_lines():
        if line.startswith("data: "):
            content = line[6:].strip()
            if content == "[DONE]":
                break
            try:
                data = json.loads(content)
                if data["type"] == "text":
                    full_content += data["data"]["content"]
            except json.JSONDecodeError:
                pass
    return full_content

def assert_response_format(data: Dict[str, Any], scenario: str):
    """Validate response structure based on scenario."""
    if scenario == "chat_response":
        assert "assistant_response" in data
        assert "session_id" in data
        assert "metadata" in data
        assert "reasoning" in data
    elif scenario == "session_info":
        assert "session_id" in data
        assert "status" in data
        assert "created_at" in data
