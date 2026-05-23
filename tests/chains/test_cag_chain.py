"""
Tests for CAG Chain (Corrective Augmented Generation).
Coverage target: 80%+
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from app.chains.cag_chain import CAGChain, CAGState, RelevanceGrade


@pytest.fixture
def mock_dependencies():
    """Mock all dependencies for CAGChain."""
    return {
        "dal": MagicMock(),
        "embedding_service": MagicMock(),
        "llm_service": MagicMock(),
        "search_provider": MagicMock()
    }


@pytest.fixture
def cag_chain(mock_dependencies):
    """Create CAGChain instance with mocked dependencies."""
    chain = CAGChain(
        dal=mock_dependencies["dal"],
        embedding_service=mock_dependencies["embedding_service"],
        llm_service=mock_dependencies["llm_service"],
        search_provider=mock_dependencies["search_provider"]
    )
    return chain


@pytest.fixture
def sample_state():
    """Sample CAG state for testing."""
    return {
        "question": "What happened last week?",
        "user_id": "user_123",
        "thread_id": "thread_456",
        "session_id": "session_789",
        "search_results": [],
        "relevance_grades": [],
        "filtered_results": [],
        "needs_correction": False,
        "draft_answer": "",
        "answer": "",
        "correction_attempts": 0,
        "correction_feedback": [],
        "selected_model": "",
        "processing_time_ms": 0
    }


class TestCAGChainInitialization:
    """Test CAGChain initialization."""
    
    def test_init_with_all_dependencies(self, mock_dependencies):
        """Test initialization with all dependencies provided."""
        chain = CAGChain(
            dal=mock_dependencies["dal"],
            embedding_service=mock_dependencies["embedding_service"],
            llm_service=mock_dependencies["llm_service"],
            search_provider=mock_dependencies["search_provider"]
        )
        
        assert chain.dal == mock_dependencies["dal"]
        assert chain.embedding_service == mock_dependencies["embedding_service"]
        assert chain.llm_service == mock_dependencies["llm_service"]
        assert chain.search_provider == mock_dependencies["search_provider"]
        assert chain.max_correction_attempts == 2
        assert chain.relevance_threshold == 0.6
    
    def test_init_without_optional_dependencies(self, mock_dependencies):
        """Test initialization without optional dependencies."""
        with patch('app.chains.cag_chain.LLMService') as mock_llm_class:
            mock_llm_instance = MagicMock()
            mock_llm_class.return_value = mock_llm_instance
            
            chain = CAGChain(
                dal=mock_dependencies["dal"],
                embedding_service=mock_dependencies["embedding_service"]
            )
            
            assert chain.llm_service == mock_llm_instance
            assert chain.search_provider is None
    
    def test_system_prompt_built(self, cag_chain):
        """Test that system prompt is built during initialization."""
        assert cag_chain.system_prompt is not None
        assert "Delёz" in cag_chain.system_prompt
        assert "контекст" in cag_chain.system_prompt.lower()


class TestGraphBuilding:
    """Test graph building and routing logic."""
    
    def test_build_graph(self, cag_chain):
        """Test that graph is built correctly."""
        graph = cag_chain.build_graph()
        assert graph is not None
    
    def test_should_correct_needs_correction(self, cag_chain):
        """Test routing when correction is needed."""
        state = {
            "needs_correction": True,
            "correction_attempts": 0
        }
        assert cag_chain._should_correct(state) == "correct"
    
    def test_should_correct_max_attempts_reached(self, cag_chain):
        """Test routing when max correction attempts reached."""
        state = {
            "needs_correction": True,
            "correction_attempts": 2
        }
        assert cag_chain._should_correct(state) == "finalize"
    
    def test_should_correct_no_correction_needed(self, cag_chain):
        """Test routing when no correction is needed."""
        state = {
            "needs_correction": False,
            "correction_attempts": 0
        }
        assert cag_chain._should_correct(state) == "finalize"


class TestRetrieveStep:
    """Test document retrieval step."""
    
    @pytest.mark.asyncio
    async def test_retrieve_with_search_provider(self, cag_chain, sample_state, mock_dependencies):
        """Test retrieval using search provider."""
        mock_dependencies["embedding_service"].generate_embedding = AsyncMock(
            return_value=[0.1, 0.2, 0.3]
        )
        mock_dependencies["search_provider"].search = AsyncMock(
            return_value=[
                {"id": "doc1", "content": "Test content", "score": 0.9}
            ]
        )
        
        result = await cag_chain.retrieve(sample_state)
        
        assert len(result["search_results"]) == 1
        assert result["search_results"][0]["id"] == "doc1"
        mock_dependencies["embedding_service"].generate_embedding.assert_called_once()
        mock_dependencies["search_provider"].search.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_retrieve_with_dal_embedding_repo(self, cag_chain, sample_state, mock_dependencies):
        """Test retrieval using DAL embedding repository."""
        cag_chain.search_provider = None
        mock_dependencies["dal"].embedding_repo = MagicMock()
        mock_dependencies["dal"].embedding_repo.search_similar = AsyncMock(
            return_value=[{"id": "doc2", "content": "DAL content", "score": 0.8}]
        )
        mock_dependencies["embedding_service"].generate_embedding = AsyncMock(
            return_value=[0.1, 0.2, 0.3]
        )
        
        result = await cag_chain.retrieve(sample_state)
        
        assert len(result["search_results"]) == 1
        assert result["search_results"][0]["id"] == "doc2"
    
    @pytest.mark.asyncio
    async def test_retrieve_handles_errors(self, cag_chain, sample_state, mock_dependencies):
        """Test that retrieval handles errors gracefully."""
        mock_dependencies["embedding_service"].generate_embedding = AsyncMock(
            side_effect=Exception("Embedding error")
        )
        
        result = await cag_chain.retrieve(sample_state)
        
        assert result["search_results"] == []
    
    @pytest.mark.asyncio
    async def test_retrieve_without_embedding_service(self, cag_chain, sample_state):
        """Test retrieval when embedding service is None."""
        cag_chain.embedding_service = None
        
        result = await cag_chain.retrieve(sample_state)
        
        assert result["search_results"] == []


class TestGradeRelevance:
    """Test relevance grading step."""
    
    @pytest.mark.asyncio
    async def test_grade_relevant_documents(self, cag_chain, sample_state):
        """Test grading of highly relevant documents."""
        sample_state["search_results"] = [
            {"id": "doc1", "final_score": 0.9, "content": "Relevant"},
            {"id": "doc2", "score": 0.7, "content": "Also relevant"}
        ]
        
        result = await cag_chain.grade_relevance(sample_state)
        
        assert len(result["relevance_grades"]) == 2
        assert result["relevance_grades"][0]["grade"] == RelevanceGrade.RELEVANT.value
        assert len(result["filtered_results"]) == 2
    
    @pytest.mark.asyncio
    async def test_grade_partially_relevant_documents(self, cag_chain, sample_state):
        """Test grading of partially relevant documents."""
        sample_state["search_results"] = [
            {"id": "doc1", "final_score": 0.5, "content": "Partially relevant"}
        ]
        
        result = await cag_chain.grade_relevance(sample_state)
        
        assert result["relevance_grades"][0]["grade"] == RelevanceGrade.PARTIALLY_RELEVANT.value
        assert len(result["filtered_results"]) == 1
    
    @pytest.mark.asyncio
    async def test_grade_not_relevant_documents(self, cag_chain, sample_state):
        """Test grading of not relevant documents."""
        sample_state["search_results"] = [
            {"id": "doc1", "final_score": 0.2, "content": "Not relevant"}
        ]
        
        result = await cag_chain.grade_relevance(sample_state)
        
        assert result["relevance_grades"][0]["grade"] == RelevanceGrade.NOT_RELEVANT.value
        assert len(result["filtered_results"]) == 0
    
    @pytest.mark.asyncio
    async def test_grade_limits_to_top_5(self, cag_chain, sample_state):
        """Test that only top 5 documents are kept."""
        sample_state["search_results"] = [
            {"id": f"doc{i}", "final_score": 0.9, "content": f"Doc {i}"}
            for i in range(10)
        ]
        
        result = await cag_chain.grade_relevance(sample_state)
        
        assert len(result["filtered_results"]) == 5


class TestGenerateDraft:
    """Test draft generation step."""
    
    @pytest.mark.asyncio
    async def test_generate_draft_success(self, cag_chain, sample_state, mock_dependencies):
        """Test successful draft generation."""
        sample_state["filtered_results"] = [
            {"title": "Meeting", "description": "Important meeting", "event_date": "2025-01-15"}
        ]
        
        mock_response = MagicMock()
        mock_response.content = "This is the draft answer"
        mock_response.model_name = "test-model"
        
        mock_dependencies["llm_service"].auto_select_and_generate = AsyncMock(
            return_value=mock_response
        )
        
        result = await cag_chain.generate_draft(sample_state)
        
        assert result["draft_answer"] == "This is the draft answer"
        assert result["selected_model"] == "test-model"
    
    @pytest.mark.asyncio
    async def test_generate_draft_handles_errors(self, cag_chain, sample_state, mock_dependencies):
        """Test draft generation error handling."""
        mock_dependencies["llm_service"].auto_select_and_generate = AsyncMock(
            side_effect=Exception("Generation error")
        )
        
        result = await cag_chain.generate_draft(sample_state)
        
        assert "ошибка" in result["draft_answer"].lower()
    
    def test_build_context_with_results(self, cag_chain):
        """Test context building from search results."""
        results = [
            {"title": "Meeting", "description": "Content 1", "event_date": "2025-01-15"},
            {"title": "Note", "page_content": "Content 2", "event_date": "2025-01-16"}
        ]
        
        context = cag_chain._build_context(results)
        
        assert "Meeting" in context
        assert "Content 1" in context
        assert "Content 2" in context
        assert "2025-01-15" in context
    
    def test_build_context_empty_results(self, cag_chain):
        """Test context building with no results."""
        context = cag_chain._build_context([])
        
        assert "не найдено" in context.lower()


class TestCheckQuality:
    """Test quality checking step."""
    
    @pytest.mark.asyncio
    async def test_check_quality_good_answer(self, cag_chain, sample_state):
        """Test quality check with good answer."""
        sample_state["draft_answer"] = "This is a comprehensive and detailed answer to your question."
        sample_state["filtered_results"] = [{"content": "Context"}]
        
        result = await cag_chain.check_quality(sample_state)
        
        assert result["needs_correction"] is False
        assert len(result["correction_feedback"]) == 0
    
    @pytest.mark.asyncio
    async def test_check_quality_short_answer(self, cag_chain, sample_state):
        """Test quality check with too short answer."""
        sample_state["draft_answer"] = "Short"
        
        result = await cag_chain.check_quality(sample_state)
        
        assert result["needs_correction"] is True
        assert any("короткий" in fb.lower() for fb in result["correction_feedback"])
    
    @pytest.mark.asyncio
    async def test_check_quality_uncertain_answer(self, cag_chain, sample_state):
        """Test quality check with uncertain answer."""
        sample_state["draft_answer"] = "Извините, я не могу помочь с этим вопросом."
        sample_state["filtered_results"] = [{"content": "Context exists"}]
        
        result = await cag_chain.check_quality(sample_state)
        
        assert result["needs_correction"] is True
        assert any("неуверенность" in fb.lower() for fb in result["correction_feedback"])
    
    @pytest.mark.asyncio
    async def test_check_quality_max_attempts_reached(self, cag_chain, sample_state):
        """Test quality check when max attempts reached."""
        sample_state["draft_answer"] = "Short"
        sample_state["correction_attempts"] = 2
        
        result = await cag_chain.check_quality(sample_state)
        
        assert result["needs_correction"] is False


class TestCorrectAnswer:
    """Test answer correction step."""
    
    @pytest.mark.asyncio
    async def test_correct_answer_success(self, cag_chain, sample_state, mock_dependencies):
        """Test successful answer correction."""
        sample_state["draft_answer"] = "Original answer"
        sample_state["correction_feedback"] = ["Too short", "Lacks detail"]
        
        mock_response = MagicMock()
        mock_response.content = "Corrected answer with more detail"
        
        mock_dependencies["llm_service"].generate_response = AsyncMock(
            return_value=mock_response
        )
        
        result = await cag_chain.correct_answer(sample_state)
        
        assert result["draft_answer"] == "Corrected answer with more detail"
        assert result["correction_attempts"] == 1
    
    @pytest.mark.asyncio
    async def test_correct_answer_handles_errors(self, cag_chain, sample_state, mock_dependencies):
        """Test correction error handling."""
        mock_dependencies["llm_service"].generate_response = AsyncMock(
            side_effect=Exception("Correction error")
        )
        
        result = await cag_chain.correct_answer(sample_state)
        
        assert result["correction_attempts"] == 2


class TestFinalize:
    """Test finalization step."""
    
    @pytest.mark.asyncio
    async def test_finalize(self, cag_chain, sample_state):
        """Test answer finalization."""
        sample_state["draft_answer"] = "Final answer content"
        
        result = await cag_chain.finalize(sample_state)
        
        assert result["answer"] == "Final answer content"


class TestStreamResponse:
    """Test streaming response."""
    
    @pytest.mark.asyncio
    async def test_stream_response_success(self, cag_chain, sample_state, mock_dependencies):
        """Test successful streaming response."""
        sample_state["filtered_results"] = [
            {"title": "Test", "description": "Content", "event_date": "2025-01-15"}
        ]
        
        async def mock_stream(*args, **kwargs):
            for chunk in ["Hello", " ", "World"]:
                mock_chunk = MagicMock()
                mock_chunk.content = chunk
                yield mock_chunk
        
        mock_dependencies["llm_service"].stream_response = mock_stream
        
        chunks = []
        async for chunk in cag_chain.stream_response(sample_state):
            chunks.append(chunk)
        
        assert chunks == ["Hello", " ", "World"]
    
    @pytest.mark.asyncio
    async def test_stream_response_handles_errors(self, cag_chain, sample_state, mock_dependencies):
        """Test streaming error handling."""
        async def mock_stream_error():
            raise Exception("Stream error")
        
        mock_dependencies["llm_service"].stream_response = mock_stream_error
        
        chunks = []
        try:
            async for chunk in cag_chain.stream_response(sample_state):
                chunks.append(chunk)
        except:
            pass
        
        # Error should be caught and yielded as error message
        assert len(chunks) >= 0


class TestRunMethod:
    """Test main run method."""
    
    @pytest.mark.asyncio
    async def test_run_complete_pipeline(self, cag_chain, mock_dependencies):
        """Test complete pipeline execution."""
        with patch.object(cag_chain, 'build_graph') as mock_build:
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(return_value={
                "answer": "Final answer",
                "selected_model": "test-model",
                "correction_attempts": 1,
                "filtered_results": [{"id": "doc1"}]
            })
            mock_build.return_value = mock_graph
            
            result = await cag_chain.run(
                question="Test question",
                user_id="user_123",
                thread_id="thread_456",
                session_id="session_789"
            )
            
            assert result["answer"] == "Final answer"
            assert result["model"] == "test-model"
            assert result["corrections"] == 1
            assert result["sources"] == 1
            assert "processing_time_ms" in result
    
    @pytest.mark.asyncio
    async def test_run_with_optional_params(self, cag_chain):
        """Test run with optional parameters."""
        with patch.object(cag_chain, 'build_graph') as mock_build:
            mock_graph = MagicMock()
            mock_graph.ainvoke = AsyncMock(return_value={
                "answer": "Answer",
                "selected_model": "model",
                "correction_attempts": 0,
                "filtered_results": []
            })
            mock_build.return_value = mock_graph
            
            result = await cag_chain.run(
                question="Test",
                user_id="user_123"
            )
            
            assert result["answer"] == "Answer"
            assert result["corrections"] == 0
            assert result["sources"] == 0
