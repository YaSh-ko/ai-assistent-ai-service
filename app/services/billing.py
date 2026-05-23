"""
Billing-сервис: расчёт стоимости токенов GigaChat.

Как использовать:
    from app.services.billing import BillingService

    billing = BillingService()
    cost = billing.calculate_cost(
        model="GigaChat",
        input_tokens=150,
        output_tokens=300,
    )
    # Инкрементируем Prometheus-метрики
    billing.record(model="GigaChat", input_tokens=150, output_tokens=300)
"""

from app.monitoring.metrics import ai_tokens_total, ai_cost_total_rub


# GigaChat Pricing (RUB per 1000 tokens)
PRICING: dict[str, dict[str, float]] = {
    "GigaChat": {
        "input": 0.20,   # руб / 1К токенов
        "output": 0.20,
    },
    "GigaChat-Pro": {
        "input": 2.50,
        "output": 2.50,
    },
    "GigaChat-Max": {
        "input": 8.00,
        "output": 8.00,
    },
    # Используем GigaChat как дефолт для неизвестных моделей
    "default": {
        "input": 0.20,
        "output": 0.20,
    },
}


class BillingService:
    """
    Billing service for token cost calculation.
    """

    _instance: "BillingService | None" = None

    def __new__(cls) -> "BillingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_pricing(self, model: str) -> dict[str, float]:
        """Get pricing scheme for the specified model."""
        for key in PRICING:
            if key != "default" and model.startswith(key):
                return PRICING[key]
        return PRICING["default"]

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate cost in RUB."""
        pricing = self.get_pricing(model)
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000
        return round(cost, 4)

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Record tokens and cost to Prometheus metrics."""
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        ai_tokens_total.labels(model=model, token_type="input").inc(input_tokens)
        ai_tokens_total.labels(model=model, token_type="output").inc(output_tokens)
        ai_cost_total_rub.labels(model=model).inc(cost)

        return cost


billing_service = BillingService()
