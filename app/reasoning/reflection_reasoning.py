"""
Reflection/Critic Loops Reasoning Engine

This engine implements a self-reflective reasoning pattern:
1. Generate initial answer
2. Critique the answer
3. Refine based on critique
4. Repeat for N iterations or until quality threshold met
"""

import time
import logging
from typing import Any, Dict, List, Optional
from app.interfaces.model_provider import IModelProvider
from app.reasoning.base_reasoning import BaseReasoning
from app.reasoning.types import ReasoningResult, ReasoningStep, ReasoningStatus

logger = logging.getLogger(__name__)


class ReflectionReasoning(BaseReasoning):
    """
    Reflection/Critic Loops reasoning implementation.
    
    Uses iterative refinement through self-critique:
    - Generate answer
    - Critique answer
    - Refine based on critique
    - Repeat until convergence or max iterations
    """
    
    def __init__(
        self,
        model_provider: IModelProvider,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Reflection reasoning engine.
        
        Args:
            model_provider: LLM provider for generation and critique
            config: Configuration dict with:
                - max_iterations: Maximum reflection loops (default: 3)
                - quality_threshold: Stop if quality score >= threshold (default: 0.8)
                - critique_temperature: Temperature for critique (default: 0.3)
                - refinement_temperature: Temperature for refinement (default: 0.7)
        """
        super().__init__()
        self.model = model_provider
        self.config = config or {}
        
        self.max_iterations = self.config.get("max_iterations", 3)
        self.quality_threshold = self.config.get("quality_threshold", 0.8)
        self.critique_temp = self.config.get("critique_temperature", 0.3)
        self.refinement_temp = self.config.get("refinement_temperature", 0.7)
        
        self._metadata.update({
            "type": "ReflectionReasoning",
            "version": "1.0.0",
            "config": self.config
        })
        
        logger.info(f"ReflectionReasoning initialized: max_iterations={self.max_iterations}, "
                   f"quality_threshold={self.quality_threshold}")
    
    async def _perform_reasoning(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Execute reflection/critic loops reasoning.
        
        Args:
            query: User question
            context: Optional context
            
        Returns:
            Final refined answer
        """
        context = context or {}
        
        # Step 1: Generate initial answer
        logger.info("Step 1: Generate initial answer")
        initial_answer = await self._generate_initial_answer(query, context)
        
        current_answer = initial_answer
        best_answer = initial_answer
        best_quality = 0.0
        
        # Reflection loop
        for iteration in range(self.max_iterations):
            logger.info(f"Reflection iteration {iteration + 1}/{self.max_iterations}")
            
            # Step 2: Critique current answer
            critique = await self._critique_answer(query, current_answer, context, iteration)
            
            # Step 3: Evaluate quality
            quality_score = await self._evaluate_quality(query, current_answer, critique, iteration)
            
            # Track best answer
            if quality_score > best_quality:
                best_quality = quality_score
                best_answer = current_answer
            
            # Check if quality threshold met
            if quality_score >= self.quality_threshold:
                logger.info(f"Quality threshold met: {quality_score:.2f} >= {self.quality_threshold}")
                break
            
            # Step 4: Refine based on critique
            if iteration < self.max_iterations - 1:  # Don't refine on last iteration
                current_answer = await self._refine_answer(
                    query, current_answer, critique, context, iteration
                )
        
        logger.info(f"Reflection complete: best_quality={best_quality:.2f}")
        return best_answer
    
    async def _generate_initial_answer(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> str:
        """Generate initial answer to the query."""
        start_time = time.time()
        
        prompt = self._build_initial_prompt(query, context)
        
        response = await self.model.generate(
            prompt=prompt,
            temperature=self.refinement_temp
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        self._add_step({
            "step_number": 1,
            "description": "Generate initial answer",
            "action": "generate",
            "action_input": {"query": query},
            "observation": response.content,
            "thought": "Creating first draft answer based on query and context",
            "duration_ms": duration_ms,
            "status": ReasoningStatus.COMPLETED,
            "metadata": None
        })
        
        return response.content
    
    async def _critique_answer(
        self,
        query: str,
        answer: str,
        context: Dict[str, Any],
        iteration: int
    ) -> str:
        """Generate critique of current answer."""
        start_time = time.time()
        
        prompt = self._build_critique_prompt(query, answer, context)
        
        response = await self.model.generate(
            prompt=prompt,
            temperature=self.critique_temp
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        self._add_step({
            "step_number": len(self._steps) + 1,
            "description": f"Critique answer (iteration {iteration + 1})",
            "action": "critique",
            "action_input": {"answer": answer[:200] + "..."},
            "observation": response.content,
            "thought": "Analyzing answer for accuracy, completeness, and clarity",
            "duration_ms": duration_ms,
            "status": ReasoningStatus.COMPLETED,
            "metadata": None
        })
        
        return response.content
    
    async def _evaluate_quality(
        self,
        query: str,
        answer: str,
        critique: str,
        iteration: int
    ) -> float:
        """Evaluate quality of current answer based on critique."""
        start_time = time.time()
        
        prompt = self._build_evaluation_prompt(query, answer, critique)
        
        response = await self.model.generate(
            prompt=prompt,
            temperature=0.1  # Low temperature for consistent scoring
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Extract quality score from response
        quality_score = self._parse_quality_score(response.content)
        
        self._add_step({
            "step_number": len(self._steps) + 1,
            "description": f"Evaluate quality (iteration {iteration + 1})",
            "action": "evaluate",
            "action_input": {"critique": critique[:200] + "..."},
            "observation": f"Quality score: {quality_score:.2f}",
            "thought": "Assessing answer quality based on critique",
            "duration_ms": duration_ms,
            "status": ReasoningStatus.COMPLETED,
            "metadata": {"quality_score": quality_score}
        })
        
        return quality_score
    
    async def _refine_answer(
        self,
        query: str,
        current_answer: str,
        critique: str,
        context: Dict[str, Any],
        iteration: int
    ) -> str:
        """Refine answer based on critique."""
        start_time = time.time()
        
        prompt = self._build_refinement_prompt(query, current_answer, critique, context)
        
        response = await self.model.generate(
            prompt=prompt,
            temperature=self.refinement_temp
        )
        
        duration_ms = (time.time() - start_time) * 1000
        
        self._add_step({
            "step_number": len(self._steps) + 1,
            "description": f"Refine answer (iteration {iteration + 1})",
            "action": "refine",
            "action_input": {"critique": critique[:200] + "..."},
            "observation": response.content,
            "thought": "Improving answer based on critique feedback",
            "duration_ms": duration_ms,
            "status": ReasoningStatus.COMPLETED,
            "metadata": None
        })
        
        return response.content
    
    def _build_initial_prompt(self, query: str, context: Dict[str, Any]) -> str:
        """Build prompt for initial answer generation."""
        context_str = ""
        if context:
            context_str = f"\n\nКонтекст:\n{self._format_context(context)}"
        
        return f"""Ответь на следующий вопрос подробно и точно.

Вопрос: {query}{context_str}

Твой ответ:"""
    
    def _build_critique_prompt(self, query: str, answer: str, context: Dict[str, Any]) -> str:
        """Build prompt for critiquing an answer."""
        return f"""Ты критик, который оценивает качество ответов. Проанализируй следующий ответ и укажи его недостатки.

Вопрос: {query}

Ответ для анализа:
{answer}

Проанализируй ответ по следующим критериям:
1. Точность: Правильна ли информация?
2. Полнота: Охвачены ли все аспекты вопроса?
3. Ясность: Понятен ли ответ?
4. Релевантность: Отвечает ли на заданный вопрос?

Твоя критика (укажи конкретные недостатки и предложения по улучшению):"""
    
    def _build_evaluation_prompt(self, query: str, answer: str, critique: str) -> str:
        """Build prompt for evaluating answer quality."""
        return f"""Оцени качество ответа по шкале от 0.0 до 1.0 на основе критики.

Вопрос: {query}

Ответ:
{answer}

Критика:
{critique}

Оцени качество ответа числом от 0.0 (очень плохо) до 1.0 (отлично).
Учитывай точность, полноту, ясность и релевантность.

Ответь ТОЛЬКО числом (например: 0.75):"""
    
    def _build_refinement_prompt(
        self,
        query: str,
        current_answer: str,
        critique: str,
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for refining answer based on critique."""
        return f"""Улучши ответ на основе полученной критики.

Вопрос: {query}

Текущий ответ:
{current_answer}

Критика:
{critique}

Создай улучшенную версию ответа, учитывая все замечания из критики.
Сохрани правильные части оригинального ответа и исправь недостатки.

Улучшенный ответ:"""
    
    def _parse_quality_score(self, response: str) -> float:
        """Parse quality score from model response."""
        try:
            # Try to extract number from response
            import re
            numbers = re.findall(r'0\.\d+|1\.0|0|1', response)
            if numbers:
                score = float(numbers[0])
                return max(0.0, min(1.0, score))  # Clamp to [0, 1]
        except (ValueError, IndexError):
            pass
        
        # Default to medium quality if parsing fails
        logger.warning(f"Failed to parse quality score from: {response[:100]}")
        return 0.5
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dictionary for prompt."""
        lines = []
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                lines.append(f"{key}: {str(value)[:200]}...")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the reasoning engine."""
        return {
            "engine_type": "reflection",
            "max_iterations": self.max_iterations,
            "quality_threshold": self.quality_threshold,
            "critique_temperature": self.critique_temp,
            "refinement_temperature": self.refinement_temp,
            "total_steps": len(self._steps)
        }
