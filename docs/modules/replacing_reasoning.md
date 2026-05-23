# Руководство по добавлению нового Reasoning Engine

## Обзор

Данное руководство описывает процесс добавления нового алгоритма рассуждения (reasoning engine) в Python AI Service. Система поддерживает различные подходы к рассуждению: Chain-of-Thought, Reflection/Critic Loops и другие.

## Архитектура Reasoning

### Компоненты

```
ReasoningFactory (Фабрика)
    ↓
IReasoningEngine (Интерфейс)
    ↓
BaseReasoning (Базовый класс)
    ↓
Конкретные реализации:
    • CoTReasoning (Chain-of-Thought)
    • ReflectionReasoning (Reflection/Critic)
    • YourNewReasoning ← добавляем здесь
    ↓
Provider обертки:
    • CoTProvider
    • ReflectionProvider
    • YourNewProvider
```

### Интерфейс IReasoningEngine

Все reasoning engines должны реализовывать интерфейс `IReasoningEngine`:

```python
# app/interfaces/reasoning_engine.py

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class ReasoningStep:
    """Шаг рассуждения."""
    step_number: int
    step_type: str  # "understand", "plan", "execute", "verify", etc.
    content: str
    metadata: Dict[str, Any] = None

@dataclass
class ReasoningResult:
    """Результат рассуждения."""
    final_answer: str
    reasoning_steps: List[ReasoningStep]
    confidence: float  # 0.0 - 1.0
    metadata: Dict[str, Any] = None


class IReasoningEngine(ABC):
    """Интерфейс для движков рассуждения."""
    
    @abstractmethod
    async def reason(
        self,
        query: str,
        context: Optional[str] = None,
        **kwargs
    ) -> ReasoningResult:
        """
        Выполнить процесс рассуждения.
        
        Args:
            query: Вопрос/задача для рассуждения
            context: Дополнительный контекст
            **kwargs: Дополнительные параметры
            
        Returns:
            ReasoningResult с финальным ответом и шагами
        """
        pass
    
    @abstractmethod
    def get_reasoning_steps(self) -> List[ReasoningStep]:
        """Получить список шагов рассуждения."""
        pass
    
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Получить метаданные о процессе рассуждения."""
        pass
```

## Шаги по добавлению нового Reasoning Engine

### Шаг 1: Создание базовой реализации

Создайте файл в `app/reasoning/`:

```python
# app/reasoning/your_reasoning.py

import logging
from typing import Dict, List, Any, Optional
from app.reasoning.base_reasoning import BaseReasoning
from app.interfaces.reasoning_engine import ReasoningResult, ReasoningStep
from app.interfaces.model_provider import IModelProvider

logger = logging.getLogger(__name__)


class YourReasoning(BaseReasoning):
    """
    Ваш кастомный алгоритм рассуждения.
    
    Пример: Tree-of-Thoughts, Self-Consistency, или другой подход.
    """
    
    def __init__(
        self,
        model_provider: IModelProvider,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Инициализация reasoning engine.
        
        Args:
            model_provider: Провайдер LLM модели
            config: Конфигурация алгоритма
        """
        super().__init__()
        
        self.model_provider = model_provider
        self.config = config or {}
        
        # Параметры из конфигурации
        self.max_iterations = self.config.get("max_iterations", 5)
        self.temperature = self.config.get("temperature", 0.7)
        self.enable_verification = self.config.get("enable_verification", True)
        
        logger.info(f"Initialized YourReasoning with config: {self.config}")
    
    async def reason(
        self,
        query: str,
        context: Optional[str] = None,
        **kwargs
    ) -> ReasoningResult:
        """
        Выполнить процесс рассуждения.
        
        Args:
            query: Вопрос для рассуждения
            context: Дополнительный контекст
            
        Returns:
            ReasoningResult с ответом и шагами
        """
        logger.info(f"Starting reasoning for query: {query[:100]}...")
        
        try:
            # Шаг 1: Инициализация
            await self._step_initialize(query, context)
            
            # Шаг 2: Основной процесс рассуждения
            answer = await self._step_main_reasoning(query, context)
            
            # Шаг 3: Верификация (опционально)
            if self.enable_verification:
                answer = await self._step_verify(query, answer)
            
            # Шаг 4: Финализация
            final_answer = await self._step_finalize(answer)
            
            # Формирование результата
            result = ReasoningResult(
                final_answer=final_answer,
                reasoning_steps=self._steps.copy(),
                confidence=self._calculate_confidence(),
                metadata=self.get_metadata()
            )
            
            logger.info(f"Reasoning completed. Steps: {len(self._steps)}")
            return result
        
        except Exception as e:
            logger.error(f"Error during reasoning: {e}")
            raise
    
    async def _step_initialize(self, query: str, context: Optional[str]):
        """Шаг 1: Инициализация и анализ запроса."""
        logger.debug("Step 1: Initialize")
        
        prompt = f"""Проанализируй следующий запрос:

Запрос: {query}

{f"Контекст: {context}" if context else ""}

Определи:
1. Тип задачи
2. Ключевые элементы
3. Требуемый подход к решению
"""
        
        response = await self.model_provider.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=500
        )
        
        self._add_step({
            "step_type": "initialize",
            "content": response.content,
            "metadata": {"tokens": response.usage}
        })
    
    async def _step_main_reasoning(
        self,
        query: str,
        context: Optional[str]
    ) -> str:
        """Шаг 2: Основной процесс рассуждения."""
        logger.debug("Step 2: Main reasoning")
        
        # Ваша логика рассуждения
        # Например, итеративное улучшение, древо мыслей, и т.д.
        
        current_answer = ""
        
        for iteration in range(self.max_iterations):
            logger.debug(f"Iteration {iteration + 1}/{self.max_iterations}")
            
            prompt = self._build_reasoning_prompt(
                query,
                context,
                current_answer,
                iteration
            )
            
            response = await self.model_provider.generate(
                prompt=prompt,
                temperature=self.temperature,
                max_tokens=1000
            )
            
            current_answer = response.content
            
            self._add_step({
                "step_type": "reasoning",
                "content": current_answer,
                "metadata": {
                    "iteration": iteration + 1,
                    "tokens": response.usage
                }
            })
            
            # Проверка условия остановки
            if self._should_stop(current_answer, iteration):
                logger.debug(f"Stopping at iteration {iteration + 1}")
                break
        
        return current_answer
    
    def _build_reasoning_prompt(
        self,
        query: str,
        context: Optional[str],
        previous_answer: str,
        iteration: int
    ) -> str:
        """Построение промпта для рассуждения."""
        if iteration == 0:
            # Первая итерация
            prompt = f"""Ответь на следующий вопрос, используя пошаговое рассуждение:

Вопрос: {query}

{f"Контекст: {context}" if context else ""}

Подумай внимательно и дай развернутый ответ.
"""
        else:
            # Последующие итерации
            prompt = f"""Улучши предыдущий ответ:

Вопрос: {query}

Предыдущий ответ:
{previous_answer}

Что можно улучшить? Дай более точный и полный ответ.
"""
        
        return prompt
    
    def _should_stop(self, answer: str, iteration: int) -> bool:
        """Проверка условия остановки."""
        # Пример: остановка если ответ достаточно длинный
        if len(answer) > 500:
            return True
        
        # Или если достигнут максимум итераций
        if iteration >= self.max_iterations - 1:
            return True
        
        return False
    
    async def _step_verify(self, query: str, answer: str) -> str:
        """Шаг 3: Верификация ответа."""
        logger.debug("Step 3: Verify")
        
        prompt = f"""Проверь правильность следующего ответа:

Вопрос: {query}

Ответ:
{answer}

Оцени:
1. Корректность
2. Полноту
3. Логичность

Если нужно, предложи исправления.
"""
        
        response = await self.model_provider.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=500
        )
        
        self._add_step({
            "step_type": "verify",
            "content": response.content,
            "metadata": {"tokens": response.usage}
        })
        
        # Если верификация предлагает исправления, применяем их
        if "исправление" in response.content.lower():
            return response.content
        
        return answer
    
    async def _step_finalize(self, answer: str) -> str:
        """Шаг 4: Финализация ответа."""
        logger.debug("Step 4: Finalize")
        
        # Опционально: форматирование финального ответа
        prompt = f"""Отформатируй следующий ответ для пользователя:

{answer}

Сделай его четким, структурированным и понятным.
"""
        
        response = await self.model_provider.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1000
        )
        
        self._add_step({
            "step_type": "finalize",
            "content": response.content,
            "metadata": {"tokens": response.usage}
        })
        
        return response.content
    
    def _calculate_confidence(self) -> float:
        """Расчет уверенности в ответе."""
        # Пример: на основе количества итераций
        iterations = len([s for s in self._steps if s["step_type"] == "reasoning"])
        
        if iterations >= self.max_iterations:
            return 0.9
        elif iterations >= self.max_iterations // 2:
            return 0.7
        else:
            return 0.5
    
    def get_metadata(self) -> Dict[str, Any]:
        """Получить метаданные."""
        return {
            "engine": "your_reasoning",
            "config": self.config,
            "total_steps": len(self._steps),
            "iterations": len([s for s in self._steps if s["step_type"] == "reasoning"])
        }
```

### Шаг 2: Создание Provider обертки

Создайте файл в `app/providers/reasoning/`:

```python
# app/providers/reasoning/your_provider.py

import logging
from typing import Dict, List, Any, Optional
from app.interfaces.reasoning_engine import IReasoningEngine, ReasoningResult, ReasoningStep
from app.interfaces.model_provider import IModelProvider
from app.reasoning.your_reasoning import YourReasoning

logger = logging.getLogger(__name__)


class YourProvider(IReasoningEngine):
    """
    Provider обертка для YourReasoning.
    Реализует интерфейс IReasoningEngine.
    """
    
    def __init__(
        self,
        model_provider: IModelProvider,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Инициализация провайдера.
        
        Args:
            model_provider: Провайдер LLM модели
            config: Конфигурация
        """
        self.reasoning_engine = YourReasoning(
            model_provider=model_provider,
            config=config
        )
        logger.info("YourProvider initialized")
    
    async def reason(
        self,
        query: str,
        context: Optional[str] = None,
        **kwargs
    ) -> ReasoningResult:
        """Выполнить рассуждение."""
        return await self.reasoning_engine.reason(query, context, **kwargs)
    
    def get_reasoning_steps(self) -> List[ReasoningStep]:
        """Получить шаги рассуждения."""
        return self.reasoning_engine.get_reasoning_steps()
    
    def get_metadata(self) -> Dict[str, Any]:
        """Получить метаданные."""
        return self.reasoning_engine.get_metadata()
```

### Шаг 3: Добавление конфигурации

Обновите `app/core/config.py`:

```python
# app/core/config.py

class Settings(BaseSettings):
    # ... существующие настройки ...
    
    # Your Reasoning Configuration
    YOUR_REASONING_CONFIG: Dict[str, Any] = {
        "max_iterations": int(os.getenv("YOUR_REASONING_MAX_ITERATIONS", "5")),
        "temperature": float(os.getenv("YOUR_REASONING_TEMPERATURE", "0.7")),
        "enable_verification": os.getenv("YOUR_REASONING_ENABLE_VERIFICATION", "True").lower() == "true",
    }
    
    REASONING_CONFIG: Dict[str, Any] = {
        "default_engine": os.getenv("DEFAULT_REASONING_ENGINE", "cot"),
        "cot": COT_CONFIG,
        "reflection": REFLECTION_CONFIG,
        "your_reasoning": YOUR_REASONING_CONFIG,  # ← добавить
        "task_mapping": {
            "simple_question": "cot",
            "dialogue": "cot",
            "analysis": "reflection",
            "complex": "your_reasoning"  # ← можно использовать для определенных задач
        }
    }
```

### Шаг 4: Регистрация в фабрике

Обновите `app/factory/reasoning_factory.py`:

```python
# app/factory/reasoning_factory.py

from app.providers.reasoning.your_provider import YourProvider

class ReasoningFactory:
    _instances: Dict[str, IReasoningEngine] = {}
    
    @classmethod
    def get_reasoning_engine(cls, engine_type: str = "cot") -> IReasoningEngine:
        """Получить reasoning engine."""
        if engine_type not in cls._instances:
            if engine_type == "cot":
                cls._instances[engine_type] = cls.create_cot_provider()
            elif engine_type == "reflection":
                cls._instances[engine_type] = cls.create_reflection_provider()
            elif engine_type == "your_reasoning":  # ← добавить
                cls._instances[engine_type] = cls.create_your_provider()
            else:
                raise ValueError(f"Unknown reasoning engine: {engine_type}")
        
        return cls._instances[engine_type]
    
    @classmethod
    def create_your_provider(cls) -> YourProvider:
        """Создать YourProvider."""
        model_provider = ModelFactory.get_model(settings.CURRENT_MODEL)
        config = settings.REASONING_CONFIG.get("your_reasoning", settings.YOUR_REASONING_CONFIG)
        
        return YourProvider(
            model_provider=model_provider,
            config=config
        )
```

### Шаг 5: Добавление переменных окружения

Обновите `.env`:

```bash
# Your Reasoning Configuration
YOUR_REASONING_MAX_ITERATIONS=5
YOUR_REASONING_TEMPERATURE=0.7
YOUR_REASONING_ENABLE_VERIFICATION=True

# Установить как движок по умолчанию (опционально)
# DEFAULT_REASONING_ENGINE=your_reasoning
```

### Шаг 6: Тестирование

Создайте тестовый скрипт:

```python
# scripts/test_your_reasoning.py

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.factory.reasoning_factory import ReasoningFactory
from app.factory.model_factory import ModelFactory


async def test_your_reasoning():
    """Тест нового reasoning engine."""
    print("=" * 60)
    print("Testing Your Reasoning Engine")
    print("=" * 60)
    
    try:
        # 1. Получить reasoning engine
        print("\n1. Getting reasoning engine...")
        engine = ReasoningFactory.get_reasoning_engine("your_reasoning")
        print(f"✓ Engine created: {engine.__class__.__name__}")
        
        # 2. Тест простого вопроса
        print("\n2. Testing simple question...")
        query = "Что такое искусственный интеллект?"
        
        result = await engine.reason(query)
        
        print(f"✓ Reasoning completed")
        print(f"  Steps: {len(result.reasoning_steps)}")
        print(f"  Confidence: {result.confidence}")
        print(f"\nFinal Answer:")
        print(result.final_answer[:200] + "...")
        
        # 3. Вывод шагов
        print("\n3. Reasoning steps:")
        for i, step in enumerate(result.reasoning_steps, 1):
            print(f"\n  Step {i} ({step.step_type}):")
            print(f"  {step.content[:100]}...")
        
        # 4. Метаданные
        print("\n4. Metadata:")
        metadata = engine.get_metadata()
        for key, value in metadata.items():
            print(f"  {key}: {value}")
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n5. Cleaning up...")
        await ModelFactory.close_all()
        print("✓ Resources cleaned up")


if __name__ == "__main__":
    asyncio.run(test_your_reasoning())
```

Запустите тест:

```bash
python3 scripts/test_your_reasoning.py
```

## Примеры алгоритмов

### Пример 1: Tree-of-Thoughts

```python
class TreeOfThoughtsReasoning(BaseReasoning):
    """Алгоритм Tree-of-Thoughts."""
    
    async def reason(self, query: str, context: Optional[str] = None, **kwargs) -> ReasoningResult:
        # 1. Генерация нескольких начальных мыслей
        thoughts = await self._generate_initial_thoughts(query, num_thoughts=3)
        
        # 2. Оценка каждой мысли
        scored_thoughts = await self._evaluate_thoughts(thoughts, query)
        
        # 3. Выбор лучших и развитие
        best_thoughts = sorted(scored_thoughts, key=lambda x: x["score"], reverse=True)[:2]
        
        # 4. Рекурсивное развитие лучших веток
        final_answers = []
        for thought in best_thoughts:
            answer = await self._develop_thought(thought, query, depth=3)
            final_answers.append(answer)
        
        # 5. Выбор финального ответа
        final_answer = await self._select_best_answer(final_answers, query)
        
        return ReasoningResult(
            final_answer=final_answer,
            reasoning_steps=self._steps,
            confidence=0.9
        )
```

### Пример 2: Self-Consistency

```python
class SelfConsistencyReasoning(BaseReasoning):
    """Алгоритм Self-Consistency."""
    
    async def reason(self, query: str, context: Optional[str] = None, **kwargs) -> ReasoningResult:
        # 1. Генерация N независимых ответов
        num_samples = self.config.get("num_samples", 5)
        answers = []
        
        for i in range(num_samples):
            response = await self.model_provider.generate(
                prompt=query,
                temperature=0.7  # Высокая температура для разнообразия
            )
            answers.append(response.content)
            
            self._add_step({
                "step_type": "sample",
                "content": response.content,
                "metadata": {"sample_num": i + 1}
            })
        
        # 2. Анализ консистентности
        final_answer = await self._aggregate_answers(answers, query)
        
        return ReasoningResult(
            final_answer=final_answer,
            reasoning_steps=self._steps,
            confidence=self._calculate_consistency(answers)
        )
    
    async def _aggregate_answers(self, answers: List[str], query: str) -> str:
        """Агрегация ответов."""
        prompt = f"""Дано {len(answers)} ответов на вопрос: {query}

Ответы:
{chr(10).join(f"{i+1}. {ans}" for i, ans in enumerate(answers))}

Найди наиболее консистентный и правильный ответ, объединив информацию из всех вариантов.
"""
        
        response = await self.model_provider.generate(prompt=prompt, temperature=0.3)
        return response.content
```

### Пример 3: Debate-Based Reasoning

```python
class DebateReasoning(BaseReasoning):
    """Алгоритм рассуждения через дебаты."""
    
    async def reason(self, query: str, context: Optional[str] = None, **kwargs) -> ReasoningResult:
        num_rounds = self.config.get("num_rounds", 3)
        
        # Позиция "За"
        position_for = await self._generate_position(query, stance="за")
        
        # Позиция "Против"
        position_against = await self._generate_position(query, stance="против")
        
        # Раунды дебатов
        for round_num in range(num_rounds):
            # Аргумент "За"
            position_for = await self._debate_round(
                query, position_for, position_against, stance="за"
            )
            
            # Контраргумент "Против"
            position_against = await self._debate_round(
                query, position_against, position_for, stance="против"
            )
        
        # Судья выносит вердикт
        final_answer = await self._judge_debate(query, position_for, position_against)
        
        return ReasoningResult(
            final_answer=final_answer,
            reasoning_steps=self._steps,
            confidence=0.85
        )
```

## Лучшие практики

### 1. Логирование шагов

```python
def _add_step(self, step_data: Dict[str, Any]):
    """Добавить шаг с логированием."""
    step = ReasoningStep(
        step_number=len(self._steps) + 1,
        step_type=step_data["step_type"],
        content=step_data["content"],
        metadata=step_data.get("metadata", {})
    )
    
    self._steps.append(step)
    logger.debug(f"Step {step.step_number} ({step.step_type}): {step.content[:50]}...")
```

### 2. Обработка ошибок

```python
async def reason(self, query: str, **kwargs) -> ReasoningResult:
    try:
        return await self._reason_impl(query, **kwargs)
    except Exception as e:
        logger.error(f"Reasoning failed: {e}")
        
        # Fallback: простой ответ без рассуждения
        response = await self.model_provider.generate(prompt=query)
        
        return ReasoningResult(
            final_answer=response.content,
            reasoning_steps=[],
            confidence=0.3,
            metadata={"error": str(e), "fallback": True}
        )
```

### 3. Кэширование промежуточных результатов

```python
class CachedReasoning(BaseReasoning):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}
    
    async def _cached_generate(self, prompt: str, **kwargs) -> str:
        cache_key = hash(prompt)
        
        if cache_key in self._cache:
            logger.debug("Cache hit")
            return self._cache[cache_key]
        
        response = await self.model_provider.generate(prompt, **kwargs)
        self._cache[cache_key] = response.content
        
        return response.content
```

## Troubleshooting

### Проблема: Reasoning engine не регистрируется

**Решение**:
1. Проверьте импорт в `reasoning_factory.py`
2. Добавьте обработку в `get_reasoning_engine()`
3. Создайте метод `create_your_provider()`

### Проблема: Слишком много токенов

**Решение**:
1. Уменьшите `max_tokens` в конфигурации
2. Сократите промпты
3. Уменьшите количество итераций

### Проблема: Низкая уверенность

**Решение**:
1. Добавьте больше итераций
2. Улучшите промпты
3. Добавьте шаг верификации

## Ссылки

- [Architecture](../architecture.md)
- [Configuration](../configuration.md)
- [Reasoning Factory Code](../../app/factory/reasoning_factory.py)
- [IReasoningEngine Interface](../../app/interfaces/reasoning_engine.py)
- [Existing Reasoning Engines](../../app/reasoning/)
