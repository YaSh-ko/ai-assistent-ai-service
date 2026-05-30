"""
Тесты для классификатора сложности и выбора моделей.
"""

import pytest
from app.core.complexity_classifier import ComplexityClassifier, get_complexity_classifier
from app.core.model_selector import ModelSelector
from app.models.complexity_models import (
    ComplexityLevel,
    QueryContext,
    ComplexityResult,
    ModelSelectionResult
)
from app.factory.model_factory import ModelFactory


# ============================================
# ComplexityClassifier Tests
# ============================================

class TestComplexityClassifier:
    """Тесты для ComplexityClassifier."""
    
    def setup_method(self):
        """Создание классификатора перед каждым тестом."""
        self.classifier = ComplexityClassifier()
    
    # --- SIMPLE запросы ---
    
    def test_simple_greeting_hello(self):
        """Приветствие 'привет' → SIMPLE."""
        result = self.classifier.classify("Привет!")
        
        assert result.level == ComplexityLevel.SIMPLE
        assert result.confidence >= 0.8
    
    def test_simple_greeting_dobry_den(self):
        """Приветствие 'добрый день' → SIMPLE."""
        result = self.classifier.classify("Добрый день")
        
        assert result.level == ComplexityLevel.SIMPLE
    
    def test_simple_thanks(self):
        """Благодарность → SIMPLE."""
        result = self.classifier.classify("Спасибо!")
        
        assert result.level == ComplexityLevel.SIMPLE
    
    def test_simple_short_question(self):
        """Короткий вопрос → SIMPLE."""
        result = self.classifier.classify("Как тебя зовут?")
        
        assert result.level == ComplexityLevel.SIMPLE
    
    def test_simple_yes_no(self):
        """Простой ответ да/нет → SIMPLE."""
        result = self.classifier.classify("Да")
        
        assert result.level == ComplexityLevel.SIMPLE
        
        result = self.classifier.classify("Нет")
        assert result.level == ComplexityLevel.SIMPLE
    
    def test_simple_what_can_you_do(self):
        """Вопрос 'что ты умеешь' → SIMPLE."""
        result = self.classifier.classify("Что ты умеешь?")
        
        assert result.level == ComplexityLevel.SIMPLE
    
    # --- MEDIUM запросы ---
    
    def test_medium_diary_entry(self):
        """Запрос на добавление записи → MEDIUM."""
        result = self.classifier.classify("Запиши, что сегодня я чувствую себя хорошо")
        
        assert result.level == ComplexityLevel.MEDIUM
        assert result.suggested_model == "gigachat_pro"
    
    def test_medium_emotions(self):
        """Описание эмоций → MEDIUM."""
        result = self.classifier.classify("Сегодня мне грустно и тревожно, не понимаю почему")
        
        assert result.level == ComplexityLevel.MEDIUM
        assert result.suggested_model == "gigachat_pro"
    
    def test_medium_explain(self):
        """Просьба объяснить → MEDIUM."""
        result = self.classifier.classify("Расскажи про мои записи за вчера")
        
        assert result.level == ComplexityLevel.MEDIUM
    
    def test_medium_week_review(self):
        """Обзор за неделю → MEDIUM."""
        result = self.classifier.classify("Что было на этой неделе?")
        
        assert result.level == ComplexityLevel.MEDIUM
    
    # --- COMPLEX запросы ---
    
    def test_complex_pattern_analysis(self):
        """Анализ паттернов → COMPLEX."""
        result = self.classifier.classify(
            "Проанализируй мои записи за последний месяц и найди закономерности в настроении"
        )
        
        assert result.level == ComplexityLevel.COMPLEX
        assert result.suggested_model == "gigachat_max"
    
    def test_complex_compare(self):
        """Сравнение → COMPLEX."""
        result = self.classifier.classify(
            "Сравни мои эмоции в январе и феврале, есть ли различия?"
        )
        
        assert result.level == ComplexityLevel.COMPLEX
        assert result.suggested_model == "gigachat_max"
    
    def test_complex_trend_analysis(self):
        """Анализ трендов → COMPLEX."""
        result = self.classifier.classify(
            "Какие тенденции в моём настроении за полгода?"
        )
        
        assert result.level == ComplexityLevel.COMPLEX
    
    def test_complex_deep_analysis(self):
        """Глубокий анализ → COMPLEX."""
        result = self.classifier.classify(
            "Почему я всегда чувствую тревогу по понедельникам? "
            "Есть ли корреляция с событиями на работе?"
        )
        
        assert result.level == ComplexityLevel.COMPLEX
    
    def test_complex_strategy_request(self):
        """Запрос стратегии → COMPLEX."""
        result = self.classifier.classify(
            "Составь план и стратегию улучшения моего эмоционального состояния "
            "на основе анализа записей за год"
        )
        
        assert result.level == ComplexityLevel.COMPLEX
    
    def test_complex_long_query(self):
        """Очень длинный запрос → COMPLEX."""
        long_query = "Расскажи мне " + "подробно " * 50 + "о моих записях"
        result = self.classifier.classify(long_query)
        
        assert result.level == ComplexityLevel.COMPLEX
    
    # --- Тесты уверенности ---
    
    def test_confidence_high_for_patterns(self):
        """Высокая уверенность для шаблонных запросов."""
        result = self.classifier.classify("Привет")
        
        assert result.confidence >= 0.9
    
    def test_confidence_reasonable_for_ambiguous(self):
        """Разумная уверенность для запросов средней длины."""
        # Запрос без ключевых слов, но не совсем короткий
        result = self.classifier.classify("Расскажи мне что-нибудь интересное")
        
        assert 0.5 <= result.confidence <= 0.9


class TestComplexityClassifierSingleton:
    """Тесты для singleton поведения."""
    
    def test_singleton_instance(self):
        """get_complexity_classifier возвращает тот же экземпляр."""
        classifier1 = get_complexity_classifier()
        classifier2 = get_complexity_classifier()
        
        assert classifier1 is classifier2


# ============================================
# ModelSelector Tests  
# ============================================

class TestModelSelectorComplexity:
    """Тесты для ModelSelector с учётом сложности."""
    
    def setup_method(self):
        """Очистка кеша перед тестами."""
        ModelFactory.clear_cache()
    
    def test_select_model_simple_query(self):
        """Простой запрос → модель для simple."""
        provider = ModelSelector.select_model("Привет!")
        
        # simple maps to "gigachat" per MODEL_COMPLEXITY_MAP
        assert provider is not None
    
    def test_select_model_medium_query(self):
        """Средний запрос → GigaChat Pro."""
        provider = ModelSelector.select_model(
            "Запиши, что сегодня я чувствую себя отлично"
        )
        
        assert provider.name == "gigachat_pro"
    
    def test_select_model_complex_query(self):
        """Сложный запрос → GigaChat Max."""
        provider = ModelSelector.select_model(
            "Проанализируй мои записи за год и найди паттерны в настроении"
        )
        
        assert provider.name == "gigachat_max"
    
    def test_select_model_privacy_preference(self):
        """prefer_privacy=True → базовая GigaChat модель."""
        provider = ModelSelector.select_model(
            "Проанализируй мои записи за год и найди паттерны",
            prefer_privacy=True,
        )

        assert provider.name == "gigachat"
    
    def test_select_model_speed_preference_simple(self):
        """prefer_speed=True + простой запрос → модель для simple."""
        provider = ModelSelector.select_model(
            "Привет!",
            prefer_speed=True
        )
        
        assert provider is not None
    
    def test_select_model_speed_preference_complex(self):
        """prefer_speed=True + сложный запрос → соответствующая модель."""
        # Для сложного запроса prefer_speed не влияет
        provider = ModelSelector.select_model(
            "Проанализируй паттерны за год",
            prefer_speed=True
        )
        
        # Сложный запрос всё равно идёт на мощную модель
        assert provider.name in ["gigachat_pro", "gigachat_max"]


class TestModelSelectorWithDetails:
    """Тесты для select_model_with_details."""
    
    def setup_method(self):
        """Очистка кеша."""
        ModelFactory.clear_cache()
    
    def test_returns_model_selection_result(self):
        """Возвращает ModelSelectionResult."""
        result = ModelSelector.select_model_with_details("Привет!")
        
        assert isinstance(result, ModelSelectionResult)
        assert result.model_name is not None
        assert result.complexity is not None
        assert result.reason is not None
    
    def test_details_contain_complexity(self):
        """Результат содержит информацию о сложности."""
        result = ModelSelector.select_model_with_details(
            "Проанализируй мои записи"
        )
        
        assert isinstance(result.complexity, ComplexityResult)
        assert result.complexity.level is not None
        assert result.complexity.confidence >= 0
    
    def test_details_reason_for_privacy(self):
        """Причина выбора при prefer_privacy."""
        result = ModelSelector.select_model_with_details(
            "Проанализируй паттерны",
            prefer_privacy=True
        )
        
        assert "приватност" in result.reason.lower()
        assert result.model_name == "gigachat"


class TestModelSelectorLegacy:
    """Тесты для legacy методов."""
    
    def setup_method(self):
        """Очистка кеша."""
        ModelFactory.clear_cache()
    
    def test_get_model_simple_question(self):
        """Legacy: get_model('simple_question')."""
        provider = ModelSelector.get_model("simple_question")
        
        assert provider is not None
    
    def test_get_model_analysis(self):
        """Legacy: get_model('analysis')."""
        provider = ModelSelector.get_model("analysis")
        
        assert provider.name == "gigachat_pro"
    
    def test_get_model_for_query(self):
        """Legacy: get_model_for_query()."""
        provider = ModelSelector.get_model_for_query("Привет!")
        
        assert provider is not None


class TestModelSelectorForComplexity:
    """Тесты для get_model_for_complexity."""
    
    def setup_method(self):
        """Очистка кеша."""
        ModelFactory.clear_cache()
    
    def test_simple_complexity(self):
        """SIMPLE → model mapped in MODEL_COMPLEXITY_MAP."""
        from app.core.config import settings
        provider = ModelSelector.get_model_for_complexity(ComplexityLevel.SIMPLE)
        expected = settings.MODEL_COMPLEXITY_MAP.get("simple", "gigachat")
        assert provider.name == expected
    
    def test_medium_complexity(self):
        """MEDIUM → GigaChat Pro."""
        provider = ModelSelector.get_model_for_complexity(ComplexityLevel.MEDIUM)
        
        assert provider.name == "gigachat_pro"
    
    def test_complex_complexity(self):
        """COMPLEX → GigaChat Max."""
        provider = ModelSelector.get_model_for_complexity(ComplexityLevel.COMPLEX)
        
        assert provider.name == "gigachat_max"
