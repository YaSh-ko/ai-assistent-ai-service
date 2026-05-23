"""
Классификатор сложности запросов.
Определяет уровень сложности для выбора оптимальной модели.
"""

import re
from typing import Optional, List, Set
from app.models.complexity_models import (
    ComplexityLevel, 
    QueryContext, 
    ComplexityResult
)
from app.core.config import settings
from app.monitoring.logger import get_logger

logger = get_logger(__name__)


class ComplexityClassifier:
    """
    Классификатор сложности запросов.
    
    Критерии классификации:
    - SIMPLE: короткие вопросы, FAQ, приветствия, простые команды
    - MEDIUM: анализ записей, начало дневника, исследование эмоций
    - COMPLEX: поиск паттернов, глубокий анализ, сравнение периодов
    """
    
    # Паттерны для SIMPLE запросов
    SIMPLE_PATTERNS: List[str] = [
        r'^привет',
        r'^здравствуй',
        r'^добрый (день|вечер|утро)',
        r'^пока$',
        r'^спасибо',
        r'^благодар',
        r'^как дела',
        r'^что (ты )?умеешь',
        r'^помощь$',
        r'^help$',
        r'^\?+$',
        r'^да$',
        r'^нет$',
        r'^ок(ей)?$',
        r'^хорошо$',
        r'^понял',
    ]
    
    # Ключевые слова для MEDIUM запросов (анализ, дневник)
    MEDIUM_KEYWORDS: Set[str] = {
        # Дневник и записи
        'запиши', 'записать', 'добавь', 'сохрани',
        'дневник', 'запись', 'событие', 'заметка',
        # Эмоции и чувства
        'чувствую', 'ощущаю', 'эмоции', 'настроение',
        'грустно', 'радостно', 'тревожно', 'спокойно',
        # Простой анализ
        'расскажи', 'объясни', 'опиши', 'покажи',
        'вчера', 'сегодня', 'недел',  # 'недел' matches неделя/неделе/неделю
        # Средние вопросы (более специфичные)
        'почему так', 'зачем это', 'что значит', 'что было',
    }
    
    # Ключевые слова для COMPLEX запросов (глубокий анализ, паттерны)
    COMPLEX_KEYWORDS: Set[str] = {
        # Глубокий анализ
        'проанализируй', 'анализ', 'паттерн', 'закономерност',
        'тенденци', 'тренд', 'динамик', 'изменени',  # stems
        # Сравнение
        'сравни', 'сопоставь', 'различи', 'сходств',
        'корреляци', 'связь', 'зависимост',
        # Периоды и временные рамки
        'за год', 'полгод', 'за квартал', 'период',
        'истори', 'эволюци', 'прогресс',
        # Глубокие вопросы
        'почему я', 'что со мной', 'в чём причина',
        'глубин', 'подсознательн', 'мотиваци',
        # Сложные задачи
        'план', 'стратеги', 'рекомендаци', 'совет',
        'прогноз', 'предсказани', 'будущ',
    }
    
    # Пороговые значения
    SIMPLE_MAX_LENGTH = 50      # Максимальная длина для SIMPLE
    MEDIUM_MAX_LENGTH = 200     # Максимальная длина для MEDIUM
    COMPLEX_MIN_LENGTH = 300    # Минимальная длина для гарантированного COMPLEX
    
    def __init__(self):
        # Компилируем регулярные выражения для производительности
        self._simple_patterns = [
            re.compile(pattern, re.IGNORECASE | re.UNICODE)
            for pattern in self.SIMPLE_PATTERNS
        ]
    
    def classify(
        self, 
        query: str, 
        context: Optional[QueryContext] = None
    ) -> ComplexityResult:
        """
        Классифицирует запрос по уровню сложности.
        
        Args:
            query: Текст запроса пользователя
            context: Контекст запроса (опционально)
            
        Returns:
            ComplexityResult с уровнем сложности и рекомендуемой моделью
        """
        query_lower = query.lower().strip()
        query_length = len(query)
        
        # Подсчитываем ключевые слова заранее
        complex_matches = self._count_keyword_matches(query_lower, self.COMPLEX_KEYWORDS)
        medium_matches = self._count_keyword_matches(query_lower, self.MEDIUM_KEYWORDS)
        has_medium_keywords = medium_matches >= 1 or self._has_medium_keywords(query_lower)
        
        # 1. Проверяем простые паттерны (приветствия, FAQ)
        # Но только если нет MEDIUM/COMPLEX ключевых слов
        if self._is_simple_pattern(query_lower) and not has_medium_keywords and complex_matches == 0:
            return self._create_result(
                ComplexityLevel.SIMPLE,
                confidence=0.95,
                reasoning="Простой шаблонный запрос (приветствие/FAQ)"
            )
        
        # 2. Проверяем наличие COMPLEX ключевых слов
        if complex_matches >= 2 or query_length >= self.COMPLEX_MIN_LENGTH:
            return self._create_result(
                ComplexityLevel.COMPLEX,
                confidence=min(0.9, 0.6 + complex_matches * 0.1),
                reasoning=f"Сложный анализ: {complex_matches} ключевых слов, {query_length} символов"
            )
        
        # 3. Проверяем наличие MEDIUM ключевых слов
        if has_medium_keywords:
            # Если есть и COMPLEX ключевые слова, повышаем до COMPLEX
            if complex_matches >= 1:
                return self._create_result(
                    ComplexityLevel.COMPLEX,
                    confidence=0.7,
                    reasoning="Смешанный запрос с аналитическими элементами"
                )
            return self._create_result(
                ComplexityLevel.MEDIUM,
                confidence=min(0.85, 0.6 + medium_matches * 0.1),
                reasoning=f"Средняя сложность: {medium_matches} ключевых слов"
            )
        
        # 4. Проверяем очень короткие запросы
        if query_length <= self.SIMPLE_MAX_LENGTH:
            return self._create_result(
                ComplexityLevel.SIMPLE,
                confidence=0.8,
                reasoning=f"Короткий запрос ({query_length} символов)"
            )
        
        # 5. Классификация по длине (fallback)
        if query_length <= self.MEDIUM_MAX_LENGTH:
            return self._create_result(
                ComplexityLevel.SIMPLE,
                confidence=0.6,
                reasoning="Средняя длина без специфичных ключевых слов"
            )
        else:
            return self._create_result(
                ComplexityLevel.MEDIUM,
                confidence=0.6,
                reasoning=f"Длинный запрос ({query_length} символов)"
            )
    
    def _is_simple_pattern(self, query: str) -> bool:
        """Проверяет, соответствует ли запрос простым паттернам."""
        for pattern in self._simple_patterns:
            if pattern.search(query):
                return True
        return False
    
    def _has_medium_keywords(self, query: str) -> bool:
        """Проверяет наличие ключевых слов средней сложности."""
        return any(kw in query for kw in self.MEDIUM_KEYWORDS)
    
    def _has_complex_keywords(self, query: str) -> bool:
        """Проверяет наличие сложных ключевых слов."""
        return any(kw in query for kw in self.COMPLEX_KEYWORDS)
    
    def _count_keyword_matches(self, query: str, keywords: Set[str]) -> int:
        """Подсчитывает количество найденных ключевых слов."""
        return sum(1 for kw in keywords if kw in query)
    
    def _create_result(
        self, 
        level: ComplexityLevel, 
        confidence: float,
        reasoning: str
    ) -> ComplexityResult:
        """Создаёт результат классификации."""
        # Маппинг сложности на модели
        model_map = settings.MODEL_COMPLEXITY_MAP
        suggested_model = model_map.get(level.value, "gigachat")
        
        logger.debug(
            f"Classified query as {level.value} "
            f"(confidence={confidence:.2f}) -> {suggested_model}"
        )
        
        return ComplexityResult(
            level=level,
            confidence=confidence,
            reasoning=reasoning,
            suggested_model=suggested_model
        )


# Singleton instance
_classifier: Optional[ComplexityClassifier] = None


def get_complexity_classifier() -> ComplexityClassifier:
    """Получить singleton экземпляр классификатора."""
    global _classifier
    if _classifier is None:
        _classifier = ComplexityClassifier()
    return _classifier
