from app.services.context_service import ContextService

def test_context_service():
    service = ContextService()
    messages = [{"role": "user", "content": "hello"}]
    context = service.format_context(messages)
    assert "user: hello" in context
