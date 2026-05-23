import asyncio
from typing import List, Dict, Any
from app.providers.search.bm25_provider import BM25Provider
from app.providers.search.vector_search_provider import VectorSearchProvider
from app.core.config import settings


def normalize_bm25_scores(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize BM25 scores to [0, 1] range using min-max normalization.
    
    Args:
        results: List of search results with 'bm25_score' field
        
    Returns:
        Results with added 'normalized_score' field
    """
    if not results:
        return results
    
    scores = [r.get('bm25_score', 0) for r in results]
    min_score = min(scores)
    max_score = max(scores)
    
    # Avoid division by zero
    score_range = max_score - min_score
    if score_range == 0:
        for r in results:
            r['normalized_score'] = 1.0
        return results
    
    for r in results:
        score = r.get('bm25_score', 0)
        r['normalized_score'] = (score - min_score) / score_range
    
    return results


def normalize_vector_scores(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize vector similarity scores.
    For cosine similarity, scores are already in a reasonable range,
    but we apply min-max normalization for consistency.
    
    Args:
        results: List of search results with 'score' field
        
    Returns:
        Results with added 'normalized_score' field
    """
    if not results:
        return results
    
    scores = [r.get('score', 0) for r in results]
    min_score = min(scores)
    max_score = max(scores)
    
    score_range = max_score - min_score
    if score_range == 0:
        for r in results:
            r['normalized_score'] = 1.0
        return results
    
    for r in results:
        score = r.get('score', 0)
        r['normalized_score'] = (score - min_score) / score_range
    
    return results


class HybridSearchProvider:
    """
    Hybrid search provider combining BM25 (keyword) and vector (semantic) search.
    """
    
    def __init__(self, bm25_provider: BM25Provider, vector_provider: VectorSearchProvider):
        """
        Initialize hybrid search provider.
        
        Args:
            bm25_provider: BM25 search provider instance
            vector_provider: Vector search provider instance
        """
        self.bm25_provider = bm25_provider
        self.vector_provider = vector_provider
        self.bm25_weight = settings.SEARCH_CONFIG['bm25_weight']
        self.vector_weight = settings.SEARCH_CONFIG['vector_weight']
    
    async def search(
        self,
        query: str,
        query_embedding: List[float],
        k: int = 10,
        top_k: int = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining BM25 and vector search.

        Args:
            query: Text query for BM25 search.
            query_embedding: Embedding vector for semantic search.
            k: Number of top results to return (default 10).
            top_k: Optional override for internal search size; if provided, it overrides `k * 2`.
            **kwargs: Additional arguments (e.g., user_id for filtering).
        Returns:
            List of top‑k results ranked by combined score.
        """
        # Determine the number of results each provider should return.
        internal_k = top_k if top_k is not None else k * 2
        # Ensure we don't pass duplicate `top_k` to the vector provider.
        vector_kwargs = dict(kwargs)
        vector_kwargs.pop('top_k', None)
        # Run both searches in parallel.
        bm25_results, vector_results = await asyncio.gather(
            self.bm25_provider.search(query=query, k=internal_k, **kwargs),
            self.vector_provider.search(query_embedding=query_embedding, top_k=internal_k, **vector_kwargs),
        )
        
        # Normalize scores
        bm25_results = normalize_bm25_scores(bm25_results)
        vector_results = normalize_vector_scores(vector_results)
        
        # Merge results by document ID
        merged_results = {}
        
        # Process BM25 results
        for result in bm25_results:
            doc_id = str(result.get('id'))
            merged_results[doc_id] = {
                'id': result.get('id'),
                'user_id': result.get('user_id'),
                'event_date': result.get('event_date'),
                'title': result.get('title'),
                'description': result.get('description'),
                'average_intensity': result.get('average_intensity'),
                'created_at': result.get('created_at'),
                'updated_at': result.get('updated_at'),
                'bm25_score': result.get('bm25_score', 0),
                'bm25_normalized': result.get('normalized_score', 0),
                'vector_score': 0,
                'vector_normalized': 0,
                'source': 'bm25'
            }
        
        # Process vector results and merge
        for result in vector_results:
            # Try to extract entry_id from metadata
            entry_id = result.get('metadata', {}).get('entry_id')
            
            if entry_id and entry_id in merged_results:
                # Document found in both searches
                merged_results[entry_id]['vector_score'] = result.get('score', 0)
                merged_results[entry_id]['vector_normalized'] = result.get('normalized_score', 0)
                merged_results[entry_id]['source'] = 'hybrid'
            elif entry_id:
                # Document only in vector search
                merged_results[entry_id] = {
                    'id': entry_id,
                    'page_content': result.get('page_content', ''),
                    'metadata': result.get('metadata', {}),
                    'bm25_score': 0,
                    'bm25_normalized': 0,
                    'vector_score': result.get('score', 0),
                    'vector_normalized': result.get('normalized_score', 0),
                    'source': 'vector'
                }
        
        # Calculate final scores and sort
        final_results = []
        for doc_id, result in merged_results.items():
            final_score = (
                self.bm25_weight * result['bm25_normalized'] +
                self.vector_weight * result['vector_normalized']
            )
            result['final_score'] = final_score
            final_results.append(result)
        
        # Sort by final score (descending) and return top-k
        final_results.sort(key=lambda x: x['final_score'], reverse=True)
        return final_results[:k]
