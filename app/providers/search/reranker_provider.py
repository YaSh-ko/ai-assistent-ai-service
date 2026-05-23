import json
import logging
from typing import List, Dict, Any
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class RerankerProvider:
    """
    Reranker provider using LLM to score and filter documents.
    """
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        
    async def rerank(
        self, 
        query: str, 
        documents: List[Dict[str, Any]], 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents based on relevance to the query using LLM.
        
        Args:
            query: The user query.
            documents: List of documents to rerank.
            top_k: Number of top documents to return.
            
        Returns:
            List of top_k documents sorted by relevance score.
        """
        if not documents:
            return []
            
        # Prepare documents for the prompt
        docs_text = ""
        for i, doc in enumerate(documents):
            content = doc.get('description') or doc.get('page_content') or doc.get('title', '')
            docs_text += f"Document {i}:\n{content}\n\n"
            
        prompt = f"""
You are an expert relevance ranker. 
Given the following query and list of documents, rate each document's relevance to the query on a scale of 0 to 10.
0 means completely irrelevant, 10 means highly relevant and directly answers the query.

Query: {query}

{docs_text}

Return ONLY a JSON object mapping document index (as string) to relevance score (integer).
Example: {{"0": 8, "1": 3, "2": 9}}
"""
        try:
            # Call LLM
            # We use a simple model or the default one. 
            # Ideally we should use a cheaper/faster model for reranking if available.
            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1, # Low temperature for consistent scoring
                max_tokens=200
            )
            
            content = response.content.strip()
            # Clean up potential markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            scores = json.loads(content)
            
            # Assign scores to documents
            for i, doc in enumerate(documents):
                score = scores.get(str(i), 0)
                doc['rerank_score'] = score
                # Normalize to 0-1 for consistency with other scores if needed, 
                # but here we just use it for sorting.
                
            # Sort by score descending
            documents.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
            
            # Return top_k
            return documents[:top_k]
            
        except Exception as e:
            logger.error(f"Error in reranking: {e}")
            # Fallback: return original top_k
            return documents[:top_k]
