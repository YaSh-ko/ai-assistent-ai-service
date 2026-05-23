"""
Tests for app/api/threads.py - LangGraph SDK-compatible Threads API
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from fastapi import HTTPException
from app.api.threads import (
    ThreadCreateRequest,
    ThreadSearchRequest,
    ThreadHistoryRequest
)


class TestThreadCreateRequest:
    """Tests for ThreadCreateRequest model"""
    
    def test_create_minimal_request(self):
        """Test creating request with minimal data"""
        request = ThreadCreateRequest()
        assert request.metadata is None
        assert request.thread_id is None
        assert request.if_exists is None
    
    def test_create_with_metadata(self):
        """Test creating request with metadata"""
        request = ThreadCreateRequest(
            metadata={"user_id": "123"},
            thread_id="thread-1"
        )
        assert request.metadata == {"user_id": "123"}
        assert request.thread_id == "thread-1"


class TestThreadSearchRequest:
    """Tests for ThreadSearchRequest model"""
    
    def test_create_default_request(self):
        """Test creating request with defaults"""
        request = ThreadSearchRequest()
        assert request.limit == 10
        assert request.offset == 0
        assert request.metadata is None
    
    def test_create_with_params(self):
        """Test creating request with parameters"""
        request = ThreadSearchRequest(
            metadata={"user_id": "123"},
            limit=20,
            offset=10,
            status="active"
        )
        assert request.metadata == {"user_id": "123"}
        assert request.limit == 20
        assert request.offset == 10
        assert request.status == "active"
    
    def test_limit_validation(self):
        """Test limit validation (max 100)"""
        request = ThreadSearchRequest(limit=100)
        assert request.limit == 100


class TestThreadHistoryRequest:
    """Tests for ThreadHistoryRequest model"""
    
    def test_create_default_request(self):
        """Test creating request with defaults"""
        request = ThreadHistoryRequest()
        assert request.limit == 10
        assert request.before is None
    
    def test_create_with_params(self):
        """Test creating request with parameters"""
        request = ThreadHistoryRequest(
            limit=5,
            before="checkpoint-1",
            metadata={"key": "value"}
        )
        assert request.limit == 5
        assert request.before == "checkpoint-1"


@pytest.mark.asyncio
class TestThreadsAPI:
    """Tests for threads API endpoints"""
    
    @patch('app.api.threads._threads', {})
    async def test_create_thread_new(self):
        """Test creating a new thread"""
        from app.api.threads import create_thread
        
        request = ThreadCreateRequest(metadata={"user": "test"})
        thread = await create_thread(request)
        
        assert thread.thread_id is not None
        assert thread.metadata == {"user": "test"}
        assert isinstance(thread.created_at, datetime)
    
    @patch('app.api.threads._threads')
    async def test_create_thread_existing(self, mock_threads):
        """Test creating thread that already exists"""
        from app.api.threads import create_thread
        from app.models.thread import Thread
        
        # Setup existing thread
        existing_thread = Thread(
            thread_id="existing-1",
            created_at=datetime.now(timezone.utc),
            metadata={}
        )
        mock_threads.__contains__ = Mock(return_value=True)
        mock_threads.__getitem__ = Mock(return_value=existing_thread)
        
        request = ThreadCreateRequest(thread_id="existing-1")
        thread = await create_thread(request)
        
        assert thread.thread_id == "existing-1"
    
    @patch('app.api.threads._threads')
    async def test_create_thread_overwrite(self, mock_threads):
        """Test creating thread with overwrite"""
        from app.api.threads import create_thread
        
        mock_threads.__contains__ = Mock(return_value=True)
        mock_threads.__setitem__ = Mock()
        
        request = ThreadCreateRequest(
            thread_id="existing-1",
            if_exists="overwrite"
        )
        thread = await create_thread(request)
        
        assert thread.thread_id == "existing-1"
        mock_threads.__setitem__.assert_called_once()
    
    @patch('app.api.threads._threads')
    async def test_get_thread_success(self, mock_threads):
        """Test getting existing thread"""
        from app.api.threads import get_thread
        from app.models.thread import Thread
        
        mock_thread = Thread(
            thread_id="thread-1",
            created_at=datetime.now(timezone.utc),
            metadata={}
        )
        mock_threads.__contains__ = Mock(return_value=True)
        mock_threads.__getitem__ = Mock(return_value=mock_thread)
        
        thread = await get_thread("thread-1")
        assert thread.thread_id == "thread-1"
    
    @patch('app.api.threads._threads', {})
    async def test_get_thread_not_found(self):
        """Test getting non-existent thread"""
        from app.api.threads import get_thread
        
        with pytest.raises(HTTPException) as exc_info:
            await get_thread("nonexistent")
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
    
    @patch('app.api.threads._threads')
    async def test_update_thread(self, mock_threads):
        """Test updating thread metadata"""
        from app.api.threads import update_thread
        from app.models.thread import Thread
        
        mock_thread = Thread(
            thread_id="thread-1",
            created_at=datetime.now(timezone.utc),
            metadata={"old": "value"}
        )
        mock_threads.__contains__ = Mock(return_value=True)
        mock_threads.__getitem__ = Mock(return_value=mock_thread)
        
        thread = await update_thread("thread-1", metadata={"new": "value"})
        
        assert thread.metadata == {"old": "value", "new": "value"}
    
    @patch('app.api.threads._threads', {})
    async def test_update_thread_not_found(self):
        """Test updating non-existent thread"""
        from app.api.threads import update_thread
        
        with pytest.raises(HTTPException) as exc_info:
            await update_thread("nonexistent", metadata={})
        
        assert exc_info.value.status_code == 404
    
    @patch('app.api.threads._threads')
    async def test_delete_thread(self, mock_threads):
        """Test deleting thread"""
        from app.api.threads import delete_thread
        
        mock_threads.__contains__ = Mock(return_value=True)
        mock_threads.__delitem__ = Mock()
        
        result = await delete_thread("thread-1")
        
        assert result == {"status": "ok"}
        mock_threads.__delitem__.assert_called_once_with("thread-1")
    
    @patch('app.api.threads._threads', {})
    async def test_delete_thread_not_found(self):
        """Test deleting non-existent thread"""
        from app.api.threads import delete_thread
        
        with pytest.raises(HTTPException) as exc_info:
            await delete_thread("nonexistent")
        
        assert exc_info.value.status_code == 404
    
    @patch('app.api.threads._threads')
    async def test_search_threads_no_filter(self, mock_threads):
        """Test searching threads without filter"""
        from app.api.threads import search_threads
        from app.models.thread import Thread
        
        # Create mock threads
        threads = [
            Thread(
                thread_id=f"thread-{i}",
                created_at=datetime.now(timezone.utc),
                metadata={}
            )
            for i in range(5)
        ]
        mock_threads.values = Mock(return_value=threads)
        
        request = ThreadSearchRequest()
        result = await search_threads(request)
        
        assert len(result) == 5
    
    @patch('app.api.threads._threads')
    async def test_search_threads_with_metadata_filter(self, mock_threads):
        """Test searching threads with metadata filter"""
        from app.api.threads import search_threads
        from app.models.thread import Thread
        
        # Create mock threads with different metadata
        threads = [
            Thread(
                thread_id="thread-1",
                created_at=datetime.now(timezone.utc),
                metadata={"user_id": "123"}
            ),
            Thread(
                thread_id="thread-2",
                created_at=datetime.now(timezone.utc),
                metadata={"user_id": "456"}
            )
        ]
        mock_threads.values = Mock(return_value=threads)
        
        request = ThreadSearchRequest(metadata={"user_id": "123"})
        result = await search_threads(request)
        
        assert len(result) == 1
        assert result[0].thread_id == "thread-1"
    
    @patch('app.api.threads._threads')
    async def test_search_threads_pagination(self, mock_threads):
        """Test searching threads with pagination"""
        from app.api.threads import search_threads
        from app.models.thread import Thread
        
        # Create 15 mock threads
        threads = [
            Thread(
                thread_id=f"thread-{i}",
                created_at=datetime.now(timezone.utc),
                metadata={}
            )
            for i in range(15)
        ]
        mock_threads.values = Mock(return_value=threads)
        
        request = ThreadSearchRequest(limit=5, offset=5)
        result = await search_threads(request)
        
        assert len(result) == 5
    
    @patch('app.api.threads._threads')
    async def test_get_thread_history(self, mock_threads):
        """Test getting thread history"""
        from app.api.threads import get_thread_history
        from app.models.thread import Thread
        
        # Create mock thread with states
        mock_thread = Thread(
            thread_id="thread-1",
            created_at=datetime.now(timezone.utc),
            metadata={}
        )
        mock_thread._states = [
            {"values": {"messages": []}, "checkpoint": {"id": "1"}},
            {"values": {"messages": []}, "checkpoint": {"id": "2"}}
        ]
        mock_threads.__contains__ = Mock(return_value=True)
        mock_threads.__getitem__ = Mock(return_value=mock_thread)
        
        request = ThreadHistoryRequest(limit=10)
        result = await get_thread_history("thread-1", request)
        
        assert len(result) == 2
    
    @patch('app.api.threads._threads')
    async def test_get_thread_history_with_limit(self, mock_threads):
        """Test getting thread history with limit"""
        from app.api.threads import get_thread_history
        from app.models.thread import Thread
        
        mock_thread = Thread(
            thread_id="thread-1",
            created_at=datetime.now(timezone.utc),
            metadata={}
        )
        mock_thread._states = [{"id": i} for i in range(10)]
        mock_threads.__contains__ = Mock(return_value=True)
        mock_threads.__getitem__ = Mock(return_value=mock_thread)
        
        request = ThreadHistoryRequest(limit=3)
        result = await get_thread_history("thread-1", request)
        
        assert len(result) == 3
    
    @patch('app.api.threads._threads', {})
    async def test_get_thread_history_not_found(self):
        """Test getting history for non-existent thread"""
        from app.api.threads import get_thread_history
        
        with pytest.raises(HTTPException) as exc_info:
            await get_thread_history("nonexistent", ThreadHistoryRequest())
        
        assert exc_info.value.status_code == 404
