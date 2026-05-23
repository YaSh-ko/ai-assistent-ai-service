from typing import List, Dict, Any
from app.interfaces.search_provider import ISearchProvider
from app.core.config import settings
import math
import re


class BM25Provider(ISearchProvider):
    """
    BM25 search provider implementing the Okapi BM25 algorithm with configurable parameters.
    """
    
    def __init__(self, db_provider):
        self.db_provider = db_provider
    
    async def search(self, query: str, k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """
        Perform BM25 search with configurable k1 and b parameters.
        
        Args:
            query: The search query string
            k: Maximum number of results to return (can also use top_k)
            **kwargs: Additional arguments, must include 'user_id'
            
        Returns:
            List of dictionaries containing entry data and bm25_score
        """
        from app.providers.databases.postgres_provider import PostgresProvider
        user_id = kwargs.get('user_id')
        if not user_id:
            # Check in filter
            filter_criteria = kwargs.get('filter', {})
            if isinstance(filter_criteria, dict):
                user_id = filter_criteria.get('user_id')
        
        if not user_id:
            raise ValueError("user_id is required for BM25 search")
            
        k = kwargs.get('top_k', k)
        
        # Get configurable BM25 parameters
        k1 = settings.SEARCH_CONFIG.get("bm25_k1", 1.5)
        b = settings.SEARCH_CONFIG.get("bm25_b", 0.75)

        async with PostgresProvider._query_lock:
            await self.db_provider._ensure_connection()
            # 1. Get total document count (N) and average document length (avgdl) for the user
            stats_sql = """
            WITH doc_stats AS (
                SELECT 
                    id,
                    LENGTH(title || ' ' || COALESCE(description, '')) as doc_length,
                    to_tsvector('russian', title || ' ' || COALESCE(description, '')) as vec
                FROM public.entries
                WHERE user_id = $1
            )
            SELECT 
                COUNT(*) as n,
                AVG(doc_length) as avgdl
            FROM doc_stats
            """
            stats = await self.db_provider.pool.fetchrow(stats_sql, user_id)
            N = stats['n'] or 0
            avgdl = float(stats['avgdl'] or 0)
            
            if N == 0 or avgdl == 0:
                return []

            # 2. Extract query terms using PostgreSQL's Russian tokenizer
            # We use to_tsvector to get the stemmed terms (lexemes) directly
            query_terms_sql = """
            SELECT unnest(tsvector_to_array(to_tsvector('russian', $1))) as lexeme
            """
            query_terms_rows = await self.db_provider.pool.fetch(query_terms_sql, query)
            query_terms = [row['lexeme'] for row in query_terms_rows]
            
            if not query_terms:
                return []

            # 3. Calculate IDF for each query term
            term_idf = {}
            for term in query_terms:
                # Number of documents containing the term
                term_freq_sql = """
                SELECT COUNT(*) as df
                FROM public.entries
                WHERE user_id = $1 
                AND to_tsvector('russian', title || ' ' || COALESCE(description, '')) @@ to_tsquery('russian', $2)
                """
                df = await self.db_provider.pool.fetchval(term_freq_sql, user_id, term)
                
                # BM25 IDF formula: log((N - df + 0.5) / (df + 0.5))
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1)  # +1 to avoid negative values
                term_idf[term] = idf

            # 4. Get all documents for the user to calculate scores
            docs_sql = """
            SELECT 
                id,
                user_id,
                event_date,
                title,
                description,
                created_at,
                updated_at,
                LENGTH(title || ' ' || COALESCE(description, '')) as doc_length,
                to_tsvector('russian', title || ' ' || COALESCE(description, '')) as vec
            FROM public.entries
            WHERE user_id = $1
            """
            docs = await self.db_provider.pool.fetch(docs_sql, user_id)
                
            results = []
            for row in docs:
                doc = dict(row)
                doc_length = doc.pop('doc_length')
                vec_str = str(doc.pop('vec', ''))
                
                # Extract term frequencies from tsvector
                term_frequencies = {}
                if vec_str:
                    # Parse tsvector format: 'word':1,2 'another':3
                    pattern = r"'([^']+)':(\d+(?:,\d+)*)"
                    matches = re.findall(pattern, vec_str)
                    for term, positions in matches:
                        # Count number of positions to get term frequency
                        tf = len(positions.split(','))
                        term_frequencies[term] = tf
                
                # Calculate BM25 score
                score = 0.0
                for term in query_terms:
                    if term in term_frequencies:
                        tf = term_frequencies[term]
                        idf = term_idf.get(term, 0)
                        
                        # BM25 formula: idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_length / avgdl)))
                        numerator = tf * (k1 + 1)
                        denominator = tf + k1 * (1 - b + b * (doc_length / avgdl))
                        
                        if denominator > 0:
                            score += idf * (numerator / denominator)
                
                # Only include documents with non-zero score
                if score > 0:
                    doc['bm25_score'] = score
                    results.append(doc)
            
            # 5. Sort by score and return top k results
            results.sort(key=lambda x: x['bm25_score'], reverse=True)
            return results[:k]