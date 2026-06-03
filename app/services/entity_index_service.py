"""
EntityIndexService — indexes user entities in ChromaDB for semantic search.

Provides the detector with awareness of existing observations, goals, and tasks
so it can suggest updating an existing entity instead of creating a duplicate.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from app.interfaces.embeddings_provider import IEmbeddingsProvider
from app.providers.databases.postgres_provider import PostgresProvider

logger = logging.getLogger(__name__)

ENTITY_COLLECTION = "user_entities"
SIMILARITY_THRESHOLD = 0.75
MAX_RESULTS = 5
_INDEX_TTL_SECONDS = 15

_FETCH_ALL_ENTITY_IDS_SQL = """
SELECT id::text FROM public.entries WHERE user_id = $1
UNION ALL
SELECT id::text FROM public.goals WHERE user_id = $1
UNION ALL
SELECT id::text FROM public.experiments WHERE user_id = $1
"""

_FETCH_ENTITIES_SQL = """
(SELECT id::text, 'observation' AS entity_type, title, description, 'active' AS status, life_area
 FROM public.entries
 WHERE user_id = $1)

UNION ALL

(SELECT id::text, 'goal' AS entity_type, title, description, status, life_area
 FROM public.goals
 WHERE user_id = $1)

UNION ALL

(SELECT id::text, 'task' AS entity_type, title, description, status, NULL::varchar AS life_area
 FROM public.experiments
 WHERE user_id = $1)
"""


def _index_document(title: str, description: str, life_area: Optional[str]) -> str:
    t = (title or "").strip()
    if not t:
        t = (description or "").strip()[:200]
    area = (life_area or "").strip().lower()
    if area:
        return f"[{area}] {t}"[:500]
    return t[:500]


class EntityMatch:
    """A single entity match from semantic search."""

    def __init__(
        self,
        entity_id: str,
        entity_type: str,
        title: str,
        description: str,
        status: str,
        score: float,
        life_area: Optional[str] = None,
    ):
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.title = title
        self.description = description
        self.status = status
        self.score = score
        self.life_area = life_area

    def to_prompt_line(self) -> str:
        status_part = f" [{self.status}]" if self.status != "active" else ""
        return f"- [{self.entity_type}] id={self.entity_id} «{self.title}»{status_part}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "title": self.title,
            "description": self.description[:200] if self.description else "",
            "status": self.status,
            "score": round(self.score, 3),
            "life_area": self.life_area,
        }


class EntityIndexService:
    """
    Manages a ChromaDB collection of user entities for semantic dedup.

    On each detector call:
    1. Ensures user's entities are indexed (lazy, incremental)
    2. Searches for entities similar to the current conversation topic
    """

    def __init__(
        self,
        db_provider: PostgresProvider,
        embeddings_provider: IEmbeddingsProvider,
        vector_store_config: Optional[Dict[str, Any]] = None,
    ):
        self._db = db_provider
        self._embeddings = embeddings_provider
        self._collection = self._init_collection(vector_store_config)
        self._indexed_users: Dict[str, float] = {}

    def _init_collection(self, config: Optional[Dict[str, Any]] = None):
        """Create or get the user_entities ChromaDB collection."""
        import chromadb
        from app.core.config import settings

        cfg = config or settings.DATABASE_CONFIG
        host = cfg.get("chroma_host") or settings.CHROMA_SERVER_HOST
        port = cfg.get("chroma_port") or settings.CHROMA_SERVER_PORT

        if host.startswith("https://") or host.startswith("http://"):
            client = chromadb.HttpClient(host=host)
        else:
            ssl = cfg.get("chroma_ssl", settings.CHROMA_SERVER_SSL)
            if "localhost" in host or "127.0.0.1" in host or "_" in host:
                ssl = False
            client = chromadb.HttpClient(host=host, port=port, ssl=ssl)

        return client.get_or_create_collection(
            name=ENTITY_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    async def _ensure_indexed(self, user_id: str) -> None:
        """Lazy-index: fetch all user entities from PG, embed, upsert into ChromaDB."""
        await self._db._ensure_connection()

        async with PostgresProvider._query_lock:
            pg_id_rows = await self._db.pool.fetch(_FETCH_ALL_ENTITY_IDS_SQL, user_id)
        pg_ids = {r["id"] for r in pg_id_rows}

        existing_ids: set[str] = set()
        try:
            existing = self._collection.get(
                where={"user_id": user_id},
                include=[],
            )
            existing_ids = set(existing["ids"]) if existing["ids"] else set()
        except Exception as e:
            logger.warning("[EntityIndex] ChromaDB get failed (will re-index all): %s", e)

        stale_ids = existing_ids - pg_ids
        if stale_ids:
            logger.info(
                "[EntityIndex] Removing %d stale entries from ChromaDB (deleted from PG)",
                len(stale_ids),
            )
            self._collection.delete(ids=list(stale_ids))
            existing_ids -= stale_ids

        missing_ids = pg_ids - existing_ids
        last_indexed = self._indexed_users.get(user_id, 0)
        if not missing_ids and time.time() - last_indexed < _INDEX_TTL_SECONDS:
            logger.debug(
                "[EntityIndex] User %s indexed %.0fs ago (TTL %ds), skipping",
                user_id, time.time() - last_indexed, _INDEX_TTL_SECONDS,
            )
            return

        if missing_ids:
            logger.info(
                "[EntityIndex] %d entities missing from ChromaDB for user %s, indexing",
                len(missing_ids), user_id,
            )
        else:
            logger.info("[EntityIndex] === Starting indexing for user %s ===", user_id)

        async with PostgresProvider._query_lock:
            rows = await self._db.pool.fetch(_FETCH_ENTITIES_SQL, user_id)

        logger.info("[EntityIndex] PG query returned %d entities for user %s", len(rows), user_id)
        if rows:
            type_counts: dict = {}
            for r in rows:
                t = r["entity_type"]
                type_counts[t] = type_counts.get(t, 0) + 1
            logger.info("[EntityIndex] Breakdown: %s", type_counts)

        if not rows:
            logger.info("[EntityIndex] No entities found in PG for user %s", user_id)
            self._indexed_users[user_id] = time.time()
            return

        logger.info("[EntityIndex] ChromaDB has %d entities for user %s", len(existing_ids), user_id)

        new_rows = [r for r in rows if r["id"] not in existing_ids]
        if not new_rows:
            logger.info("[EntityIndex] All %d entities already indexed, nothing new", len(rows))
            self._indexed_users[user_id] = time.time()
            return

        logger.info("[EntityIndex] Need to embed %d new entities", len(new_rows))
        texts = []
        for r in new_rows:
            doc = _index_document(
                r.get("title") or "",
                r.get("description") or "",
                r.get("life_area"),
            )
            texts.append(doc)
        for i, (r, doc) in enumerate(zip(new_rows[:10], texts[:10]), start=1):
            logger.info(
                "[EntityIndex]   index #%d: [%s] id=%s area=%s title=%r doc=%r",
                i,
                r["entity_type"],
                r["id"][:8],
                r.get("life_area") or "-",
                (r.get("title") or "")[:50],
                doc[:80],
            )
        if len(new_rows) > 10:
            logger.info("[EntityIndex]   ... and %d more entities", len(new_rows) - 10)

        try:
            logger.info("[EntityIndex] Calling embeddings provider for %d texts...", len(texts))
            embeddings = await self._embeddings.embed_documents(texts)
            logger.info("[EntityIndex] Embeddings received: %d vectors, dim=%d", len(embeddings), len(embeddings[0]) if embeddings else 0)
        except Exception as e:
            logger.error("[EntityIndex] Embedding failed: %s", e, exc_info=True)
            self._indexed_users[user_id] = time.time()
            return

        ids = [r["id"] for r in new_rows]
        metadatas = [
            {
                "user_id": user_id,
                "entity_type": r["entity_type"],
                "title": r["title"] or "",
                "status": r["status"] or "active",
                "life_area": (r.get("life_area") or "") or "",
            }
            for r in new_rows
        ]
        documents = [t[:500] for t in texts]

        try:
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )
            logger.info(
                "[EntityIndex] Successfully indexed %d entities for user %s", len(ids), user_id
            )
        except Exception as e:
            logger.error("[EntityIndex] ChromaDB upsert failed: %s", e, exc_info=True)

        self._indexed_users[user_id] = time.time()

    async def force_reindex_user(self, user_id: str) -> int:
        """Удалить индекс пользователя в Chroma и заново встроить все сущности (life_area, заголовки)."""
        logger.info("[EntityIndex] === Force reindex start === user=%s", user_id)
        self._indexed_users.pop(user_id, None)
        try:
            existing = self._collection.get(where={"user_id": user_id}, include=[])
            ids = existing.get("ids") or []
            if ids:
                self._collection.delete(ids=ids)
                logger.info("[EntityIndex] Cleared %d Chroma docs for user %s", len(ids), user_id)
        except Exception as e:
            logger.warning("[EntityIndex] Chroma clear failed for user %s: %s", user_id, e)

        await self._ensure_indexed(user_id)
        try:
            after = self._collection.get(where={"user_id": user_id}, include=[])
            count = len(after.get("ids") or [])
        except Exception:
            count = 0
        logger.info("[EntityIndex] Force reindex done for user %s: %d entities", user_id, count)
        return count

    async def search(
        self,
        user_id: str,
        query_text: str,
        top_k: int = MAX_RESULTS,
        threshold: float = SIMILARITY_THRESHOLD,
    ) -> List[EntityMatch]:
        """
        Semantic search for entities similar to query_text.
        Returns matches above the similarity threshold.
        """
        logger.info(
            "[EntityIndex] === Search start === user=%s query=%r threshold=%.2f top_k=%d",
            user_id, query_text[:80], threshold, top_k,
        )
        await self._ensure_indexed(user_id)

        try:
            logger.debug("[EntityIndex] Embedding query text (%d chars)...", len(query_text))
            query_embedding = await self._embeddings.embed_query(query_text)
            logger.debug("[EntityIndex] Query embedding ready, dim=%d", len(query_embedding))
        except Exception as e:
            logger.warning(
                "[EntityIndex] Embedding failed (%s), falling back to PG text search",
                type(e).__name__,
            )
            return await self._fallback_text_search(user_id, query_text, top_k)

        n_results = max(top_k * 3, 15)
        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                where={"user_id": user_id},
                n_results=n_results,
                include=["metadatas", "documents", "distances"],
            )
        except Exception as e:
            logger.error("[EntityIndex] ChromaDB query failed: %s", e, exc_info=True)
            return await self._fallback_text_search(user_id, query_text, top_k)

        raw_count = len(results["ids"][0]) if results["ids"] and results["ids"][0] else 0
        logger.info("[EntityIndex] ChromaDB returned %d raw candidates", raw_count)

        matches: List[EntityMatch] = []
        if not results["ids"] or not results["ids"][0]:
            logger.info("[EntityIndex] No candidates found in ChromaDB")
            return matches

        below_thr = 0
        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i] if results["distances"] else 1.0
            score = 1.0 - distance
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            title = meta.get("title", "")
            life_area_raw = meta.get("life_area") or "-"
            doc = results["documents"][0][i] if results["documents"] else ""

            passed = score >= threshold
            if not passed:
                below_thr += 1
            logger.info(
                "[EntityIndex]   candidate #%d: [%s] id=%s area=%s title=%r "
                "score=%.3f dist=%.3f doc=%r %s",
                i + 1,
                meta.get("entity_type", "?"),
                doc_id[:12],
                life_area_raw,
                title[:50],
                score,
                distance,
                (doc or "")[:70],
                "PASS" if passed else "BELOW_THRESHOLD",
            )

            if not passed:
                continue

            life_area = meta.get("life_area") or None
            matches.append(
                EntityMatch(
                    entity_id=doc_id,
                    entity_type=meta.get("entity_type", "observation"),
                    title=title,
                    description=doc,
                    status=meta.get("status", "active"),
                    score=score,
                    life_area=life_area if life_area else None,
                )
            )

        matches.sort(key=lambda m: m.score, reverse=True)
        final = matches[:top_k]
        logger.info(
            "[EntityIndex] === Search result === %d matches (raw=%d below_thr=%d) "
            "threshold=%.2f top_k=%d",
            len(final),
            raw_count,
            below_thr,
            threshold,
            top_k,
        )
        for m in final:
            logger.info(
                "[EntityIndex]   MATCH: [%s] id=%s area=%s title=%r score=%.3f status=%s",
                m.entity_type,
                m.entity_id[:12],
                m.life_area or "-",
                m.title[:50],
                m.score,
                m.status,
            )
        return final

    async def _fallback_text_search(
        self,
        user_id: str,
        query_text: str,
        top_k: int = MAX_RESULTS,
    ) -> List[EntityMatch]:
        """Fallback: PostgreSQL full-text search when embeddings are unavailable.

        Uses OR-logic between terms so 'хочу похудеть к лету' matches
        entities containing any of those words (not all of them).
        """
        logger.info("[EntityIndex] === PG text search fallback === query=%r", query_text[:80])

        sql = """
        SELECT id::text, entity_type, title, description, status,
               ts_rank(vec, query) AS rank
        FROM (
            SELECT id, 'observation' AS entity_type, title, description, 'active' AS status,
                   to_tsvector('russian', COALESCE(title,'') || ' ' || COALESCE(description,'')) AS vec
            FROM public.entries WHERE user_id = $1

            UNION ALL

            SELECT id, 'goal' AS entity_type, title, description, status,
                   to_tsvector('russian', COALESCE(title,'') || ' ' || COALESCE(description,'')) AS vec
            FROM public.goals WHERE user_id = $1

            UNION ALL

            SELECT id, 'task' AS entity_type, title, description, status,
                   to_tsvector('russian', COALESCE(title,'') || ' ' || COALESCE(description,'')) AS vec
            FROM public.experiments WHERE user_id = $1
        ) AS all_entities,
        to_tsquery('russian',
            replace(plainto_tsquery('russian', $2)::text, ' & ', ' | ')
        ) AS query
        WHERE vec @@ query
        ORDER BY rank DESC
        LIMIT $3
        """

        try:
            await self._db._ensure_connection()
            async with PostgresProvider._query_lock:
                rows = await self._db.pool.fetch(sql, user_id, query_text, top_k)
        except Exception as e:
            logger.error("[EntityIndex] PG text search failed: %s", e, exc_info=True)
            return []

        logger.info("[EntityIndex] PG returned %d raw rows", len(rows))

        matches: List[EntityMatch] = []
        for r in rows:
            rank = float(r["rank"])
            m = EntityMatch(
                entity_id=r["id"],
                entity_type=r["entity_type"],
                title=r["title"] or "",
                description=(r["description"] or "")[:200],
                status=r["status"] or "active",
                score=min(rank, 1.0),
            )
            matches.append(m)
            logger.info(
                "[EntityIndex]   PG match: [%s] id=%s title=%r rank=%.4f status=%s",
                m.entity_type, m.entity_id[:12], m.title[:50], rank, m.status,
            )

        logger.info("[EntityIndex] === PG fallback result === %d matches", len(matches))
        return matches

    async def add_entity(
        self,
        user_id: str,
        entity_id: str,
        entity_type: str,
        title: str,
        description: str,
        status: str = "active",
    ) -> None:
        """Index a single newly created/updated entity immediately."""
        text = f"{title} {description}".strip()
        if not text:
            return

        try:
            embedding = await self._embeddings.embed_query(text)
        except Exception as e:
            logger.error("[EntityIndex] Single embed failed: %s", e)
            return

        try:
            self._collection.upsert(
                ids=[entity_id],
                embeddings=[embedding],
                metadatas=[
                    {
                        "user_id": user_id,
                        "entity_type": entity_type,
                        "title": title,
                        "status": status,
                    }
                ],
                documents=[text[:500]],
            )
        except Exception as e:
            logger.error("[EntityIndex] Single upsert failed: %s", e)

    def invalidate_user(self, user_id: str) -> None:
        """Force re-index on next search for this user."""
        self._indexed_users.pop(user_id, None)
