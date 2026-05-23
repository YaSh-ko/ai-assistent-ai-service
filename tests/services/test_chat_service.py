"""
Tests for ChatService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.chat.chat_service import ChatService


@pytest.fixture
def mock_rag_chain():
    chain = MagicMock()
    chain.process_user_message = AsyncMock(
        return_value=(AsyncMock(), {"complexity": "simple", "selected_model": "mock"})
    )
    return chain


@pytest.fixture
def chat_service(mock_rag_chain):
    return ChatService(rag_chain=mock_rag_chain)


class TestChatService:
    @pytest.mark.asyncio
    async def test_process_message_delegates_to_rag_chain(self, chat_service, mock_rag_chain):
        stream, state = await chat_service.process_message(
            session_id="s1",
            user_question="What is Jupiter?",
            user_id="u1",
        )
        mock_rag_chain.process_user_message.assert_called_once_with(
            session_id="s1",
            user_question="What is Jupiter?",
            user_id="u1",
            thread_id=None,
        )
        assert state["complexity"] == "simple"

    @pytest.mark.asyncio
    async def test_process_message_passes_thread_id(self, chat_service, mock_rag_chain):
        await chat_service.process_message(
            session_id="s1",
            user_question="hello",
            user_id="u1",
            thread_id="t1",
        )
        mock_rag_chain.process_user_message.assert_called_once_with(
            session_id="s1",
            user_question="hello",
            user_id="u1",
            thread_id="t1",
        )

    @pytest.mark.asyncio
    async def test_process_message_propagates_exception(self, chat_service, mock_rag_chain):
        mock_rag_chain.process_user_message = AsyncMock(side_effect=RuntimeError("chain error"))
        with pytest.raises(RuntimeError, match="chain error"):
            await chat_service.process_message("s1", "q", "u1")
