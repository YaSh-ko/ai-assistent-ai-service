import time
import logging
import asyncio
from typing import Any, Dict, List, Optional
from app.reasoning.base_reasoning import BaseReasoning
from app.reasoning.types import ReasoningResult, ReasoningStep, ReasoningStatus
from app.interfaces.model_provider import IModelProvider
from app.monitoring.metrics import ReasoningMetrics

logger = logging.getLogger(__name__)

class CoTReasoning(BaseReasoning):
    """
    Реализация рассуждения Chain-of-Thought (CoT) с 4 основными шагами:
    1. Understand (Понимание)
    2. Plan (Планирование)
    3. Execute (Выполнение)
    4. Verify (Проверка)
    
    Этот класс оркестрирует вызовы к LLM для каждого шага и собирает результаты.
    """
    
    def __init__(
        self, 
        model_provider: IModelProvider,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Инициализация движка CoT.
        
        Args:
            model_provider: Провайдер LLM модели.
            config: Конфигурация (max_depth, enable_verification и т.д.).
        """
        super().__init__()
        self.model = model_provider
        self.metrics = ReasoningMetrics()
        self.config = config or {}
        
        # Default config values
        self.max_depth = self.config.get("max_reasoning_depth", 4)
        self.enable_verification = self.config.get("enable_verification", True)
        self.timeout_per_step = self.config.get("timeout_per_step", 30)
        
        self._metadata.update({
            "type": "CoTReasoning",
            "version": "1.0.0",
            "steps": ["understand", "plan", "execute", "verify"],
            "config": self.config
        })

    async def _perform_reasoning(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]],
        **kwargs
    ) -> Any:
        """
        Основной метод выполнения рассуждения, оркестрирующий 4 шага.
        
        Args:
            query: Вопрос пользователя.
            context: Контекст (результаты поиска и т.д.).
            
        Returns:
            Финальный синтезированный ответ.
        """
        step_durations = {}
        
        try:
            # Step 1: Understand
            t0 = time.time()
            understanding = await asyncio.wait_for(
                self.understand(query, context), 
                timeout=self.timeout_per_step
            )
            step_durations["understand"] = (time.time() - t0) * 1000
            
            # Check for empty context edge case
            if not context and not understanding.get("can_answer_without_context", False):
                 # If context is empty and model thinks it needs it, we might want to stop or warn
                 logger.warning("Context is empty, reasoning might be limited.")

            # Step 2: Plan
            t0 = time.time()
            plan = await asyncio.wait_for(
                self.plan(understanding),
                timeout=self.timeout_per_step
            )
            step_durations["plan"] = (time.time() - t0) * 1000
            
            # Step 3: Execute
            t0 = time.time()
            execution_results = await asyncio.wait_for(
                self.execute(plan),
                timeout=self.timeout_per_step
            )
            step_durations["execute"] = (time.time() - t0) * 1000
            
            # Step 4: Verify
            if self.enable_verification:
                t0 = time.time()
                final_result = await asyncio.wait_for(
                    self.verify(execution_results, query),
                    timeout=self.timeout_per_step
                )
                step_durations["verify"] = (time.time() - t0) * 1000
            else:
                # If verification is disabled, just return execution results formatted
                final_result = str(execution_results)
                step_durations["verify"] = 0
            
            # Record metrics
            self.metrics.record_execution(
                success=True,
                duration_ms=sum(step_durations.values()),
                step_durations=step_durations
            )
            
            return final_result
            
        except asyncio.TimeoutError as e:
            logger.error(f"Reasoning step timed out: {str(e)}")
            self.metrics.record_execution(success=False, duration_ms=0, step_durations=step_durations)
            raise TimeoutError("Reasoning step timed out")
        except Exception as e:
            logger.error(f"Reasoning failed: {str(e)}")
            self.metrics.record_execution(success=False, duration_ms=0, step_durations=step_durations)
            raise e

    async def understand(self, query: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Шаг 1: Анализ интента пользователя и извлечение сущностей.
        
        Args:
            query: Исходный вопрос.
            context: Доступный контекст.
            
        Returns:
            Словарь с результатами анализа.
        """
        logger.info("Step 1: Understand")
        
        # Prompt for understanding
        prompt = f"""
        Analyze the following user query:
        "{query}"
        
        Context: {context}
        
        Extract:
        1. User Intent (what they want to know)
        2. Key Entities (people, places, dates, concepts)
        3. Task Type (Fact Retrieval, Pattern Finding, Time Analysis, Insight Generation)
        4. Time Range (if applicable)
        5. Emotional Context
        6. Can answer without context? (True/False)
        
        Return as JSON.
        """
        
        response = await self.model.generate(prompt=prompt)
        
        # In a real implementation, we would parse the JSON response.
        
        understanding = {
            "raw_analysis": response.content,
            "query": query,
            "context": context,
            "can_answer_without_context": "True" in response.content # simplistic check
        }
        
        self._add_step({
            "step_number": 1,
            "description": "Understand user query",
            "action": "analyze_intent",
            "action_input": query,
            "observation": "Analysis complete",
            "thought": f"User wants to know about: {query}", 
            "duration_ms": 0, 
            "status": ReasoningStatus.COMPLETED,
            "metadata": {"model": self.model.model_name}
        })
        
        return understanding

    async def plan(self, understanding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Шаг 2: Планирование стратегии и запросов к БД.
        
        Args:
            understanding: Результаты шага 1.
            
        Returns:
            План выполнения.
        """
        logger.info("Step 2: Plan")
        
        prompt = f"""
        Based on the understanding:
        {understanding['raw_analysis']}
        
        Create a plan to answer the query.
        1. Select strategy (Direct Search, Graph Analysis, Aggregation)
        2. Generate 3-5 clarifying questions if needed.
        3. List necessary data sources (PostgreSQL, Neo4j).
        
        Return as JSON.
        """
        
        response = await self.model.generate(prompt=prompt)
        
        plan = {
            "raw_plan": response.content,
            "strategy": "mixed", 
            "steps": ["query_db", "analyze_graph"] 
        }
        
        self._add_step({
            "step_number": 2,
            "description": "Plan execution strategy",
            "action": "create_plan",
            "action_input": understanding['raw_analysis'],
            "observation": "Plan created",
            "thought": "I need to check both the database and the graph.",
            "duration_ms": 0,
            "status": ReasoningStatus.COMPLETED,
            "metadata": {"model": self.model.model_name}
        })
        
        return plan

    async def execute(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Шаг 3: Выполнение запланированных действий.
        
        Args:
            plan: План из шага 2.
            
        Returns:
            Результаты выполнения (данные из БД и т.д.).
        """
        logger.info("Step 3: Execute")
        
        # Placeholder for actual execution logic (DB calls, etc.)
        
        results = {
            "db_data": "Simulated DB results",
            "graph_data": "Simulated Graph results"
        }
        
        self._add_step({
            "step_number": 3,
            "description": "Execute planned steps",
            "action": "execute_queries",
            "action_input": plan,
            "observation": str(results),
            "thought": "Gathered data from all sources.",
            "duration_ms": 0,
            "status": ReasoningStatus.COMPLETED,
            "metadata": {}
        })
        
        return results

    async def verify(self, execution_results: Dict[str, Any], original_query: str) -> str:
        """
        Шаг 4: Проверка результатов и синтез финального ответа.
        
        Args:
            execution_results: Данные из шага 3.
            original_query: Исходный вопрос пользователя.
            
        Returns:
            Финальный ответ.
        """
        logger.info("Step 4: Verify")
        
        prompt = f"""
        Original Query: {original_query}
        Execution Results: {execution_results}
        
        1. Verify if the results answer the query.
        2. Check for contradictions.
        3. Synthesize the final answer.
        """
        
        response = await self.model.generate(prompt=prompt)
        
        self._add_step({
            "step_number": 4,
            "description": "Verify and synthesize",
            "action": "synthesize_answer",
            "action_input": execution_results,
            "observation": "Answer generated",
            "thought": "The results are consistent and answer the query.",
            "duration_ms": 0,
            "status": ReasoningStatus.COMPLETED,
            "metadata": {"model": self.model.model_name}
        })
        
        return response.content
