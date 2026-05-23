from unittest.mock import MagicMock, AsyncMock
from app.chains.rag_chain import RAGChain

def test_rag_chain_build():
    # Create mock dependencies
    mock_dal = MagicMock()
    mock_embedding_service = MagicMock()
    
    # Create RAGChain with mocked dependencies
    mock_search_provider = MagicMock()
    chain = RAGChain(dal=mock_dal, embedding_service=mock_embedding_service, hybrid_search_provider=mock_search_provider)
    
    # Build the graph
    graph = chain.build_graph()
    assert graph is not None
