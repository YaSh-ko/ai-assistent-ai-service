from app.core.config import settings

def select_reasoning_engine(task_type: str) -> str:
    """
    Select the appropriate reasoning engine based on the task type.
    """
    mapping = settings.REASONING_CONFIG.get("task_mapping", {})
    return mapping.get(task_type, settings.REASONING_CONFIG.get("default_engine", "cot"))
