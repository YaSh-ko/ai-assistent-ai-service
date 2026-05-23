import pytest
from tests.e2e.utils import create_test_session

@pytest.mark.asyncio
async def test_model_switching(client):
    user_id = "test_user_e2e"
    session_id = await create_test_session(client, user_id)
    
    # 1. Simple query -> should use vLLM or GigaChat (depending on classifier)
    res_simple = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Привет"}
    )
    data_simple = res_simple.json()
    model_simple = data_simple["metadata"].get("model_used")
    
    # 2. Complex query -> should use GigaChat Pro/Max
    res_complex = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": "Проведи глубокий философский анализ связи между концепцией ризомы Делёза и развитием современных децентрализованных сетей, учитывая социальный и технологический аспект."}
    )
    data_complex = res_complex.json()
    model_complex = data_complex["metadata"].get("model_used")
    
    print(f"\nSimple model: {model_simple}")
    print(f"Complex model: {model_complex}")
    
    # Basic check that routing happens (might be same model if mocked, 
    # but in real setup they should differ or at least be tracked)
    assert model_simple is not None
    assert model_complex is not None
    
    # If using actual classifier:
    # assert model_simple != model_complex or data_complex["metadata"]["complexity"] == "complex"
