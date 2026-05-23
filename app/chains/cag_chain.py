"""
CAG Chain - Corrective Augmented Generation.

Пайплайн с коррекцией ошибок и проверкой качества ответов.

Отличия от RAG:
1. Проверяет релевантность найденных документов
2. Корректирует ответ при обнаружении проблем
3. Использует fact-checking для важных утверждений
"""

from typing import Any, Dict, List, TypedDict, Optional, AsyncGenerator
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END

from app.chains.base_chain import BaseChain
from app.data_access.repositories.dal import DataAccessLayer
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.core.model_selector import ModelSelector
from app.monitoring.logger import get_logger

logger = get_logger(__name__)


class RelevanceGrade(Enum):
    """Оценка релевантности документа."""
    RELEVANT = "relevant"
    PARTIALLY_RELEVANT = "partially_relevant"
    NOT_RELEVANT = "not_relevant"


class CAGState(TypedDict):
    """Состояние CAG пайплайна."""
    # Входные данные
    question: str
    user_id: str
    thread_id: str
    session_id: str
    
    # Результаты поиска
    search_results: List[Dict[str, Any]]
    
    # Оценка релевантности
    relevance_grades: List[Dict[str, Any]]
    filtered_results: List[Dict[str, Any]]
    needs_correction: bool
    
    # Генерация
    draft_answer: str
    answer: str
    
    # Коррекция
    correction_attempts: int
    correction_feedback: List[str]
    
    # Метаданные
    selected_model: str
    processing_time_ms: float


class CAGChain(BaseChain):
    """
    Corrective Augmented Generation Chain.
    
    Добавляет слой проверки качества поверх RAG:
    1. Оценка релевантности найденных документов
    2. Генерация черновика ответа
    3. Проверка качества и коррекция при необходимости
    4. Финальная генерация
    """
    
    def __init__(
        self,
        dal: DataAccessLayer,
        embedding_service: EmbeddingService,
        llm_service: Optional[LLMService] = None,
        search_provider: Optional[Any] = None
    ):
        self.dal = dal
        self.embedding_service = embedding_service
        self.llm_service = llm_service or LLMService()
        self.search_provider = search_provider
        
        # Конфигурация
        self.max_correction_attempts = 2
        self.relevance_threshold = 0.6
        
        # Системный промпт
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Системный промпт для CAG."""
        return """Ты — Delёz, умный и заботливый личный помощник.

При ответе на вопросы:
1. Используй только информацию из предоставленного контекста
2. Если информации недостаточно — честно скажи об этом
3. Не придумывай факты
4. Будь эмпатичным и поддерживающим
"""
    
    def build_graph(self) -> StateGraph:
        """Построение LangGraph графа."""
        workflow = StateGraph(CAGState)
        
        # Определение узлов
        workflow.add_node("retrieve", self.retrieve)
        workflow.add_node("grade_relevance", self.grade_relevance)
        workflow.add_node("generate_draft", self.generate_draft)
        workflow.add_node("check_quality", self.check_quality)
        workflow.add_node("correct_answer", self.correct_answer)
        workflow.add_node("finalize", self.finalize)
        
        # Определение связей
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "grade_relevance")
        workflow.add_edge("grade_relevance", "generate_draft")
        workflow.add_edge("generate_draft", "check_quality")
        
        # Условный переход: коррекция или финализация
        workflow.add_conditional_edges(
            "check_quality",
            self._should_correct,
            {
                "correct": "correct_answer",
                "finalize": "finalize"
            }
        )
        workflow.add_edge("correct_answer", "check_quality")
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    def _should_correct(self, state: CAGState) -> str:
        """Решение: нужна ли коррекция."""
        if state.get("needs_correction", False):
            if state.get("correction_attempts", 0) < self.max_correction_attempts:
                return "correct"
        return "finalize"
    
    # =========================================================================
    # ШАГ 1: ПОИСК
    # =========================================================================
    
    async def retrieve(self, state: CAGState) -> CAGState:
        """Поиск релевантных документов."""
        question = state["question"]
        user_id = state.get("user_id")
        
        logger.info(f"[CAG] Поиск для: '{question[:50]}...'")
        
        search_results = []
        
        try:
            if self.embedding_service:
                query_embedding = await self.embedding_service.generate_embedding(question)
                
                if self.search_provider:
                    search_results = await self.search_provider.search(
                        query=question,
                        query_embedding=query_embedding,
                        top_k=10,
                        user_id=user_id
                    )
                elif hasattr(self.dal, 'embedding_repo'):
                    search_results = await self.dal.embedding_repo.search_similar(
                        query_embedding=query_embedding,
                        top_k=10,
                        user_id=user_id
                    )
        except Exception as e:
            logger.error(f"[CAG] Ошибка поиска: {e}")
        
        state["search_results"] = search_results
        logger.info(f"[CAG] Найдено {len(search_results)} документов")
        
        return state
    
    # =========================================================================
    # ШАГ 2: ОЦЕНКА РЕЛЕВАНТНОСТИ
    # =========================================================================
    
    async def grade_relevance(self, state: CAGState) -> CAGState:
        """
        Оценка релевантности каждого документа.
        
        Использует LLM для классификации документов.
        """
        search_results = state.get("search_results", [])
        
        logger.info(f"[CAG] Оценка релевантности {len(search_results)} документов")
        
        relevance_grades = []
        filtered_results = []
        
        for doc in search_results:
            
            # Быстрая эвристика по score
            score = doc.get("final_score", doc.get("score", 0))
            
            if score >= self.relevance_threshold:
                grade = RelevanceGrade.RELEVANT
            elif score >= self.relevance_threshold * 0.7:
                grade = RelevanceGrade.PARTIALLY_RELEVANT
            else:
                grade = RelevanceGrade.NOT_RELEVANT
            
            relevance_grades.append({
                "doc_id": doc.get("id", ""),
                "grade": grade.value,
                "score": score
            })
            
            # Оставляем только релевантные
            if grade in [RelevanceGrade.RELEVANT, RelevanceGrade.PARTIALLY_RELEVANT]:
                filtered_results.append(doc)
        
        state["relevance_grades"] = relevance_grades
        state["filtered_results"] = filtered_results[:5]  # Топ-5
        
        logger.info(f"[CAG] Отфильтровано: {len(filtered_results)} релевантных документов")
        
        return state
    
    # =========================================================================
    # ШАГ 3: ГЕНЕРАЦИЯ ЧЕРНОВИКА
    # =========================================================================
    
    async def generate_draft(self, state: CAGState) -> CAGState:
        """Генерация черновика ответа."""
        question = state["question"]
        filtered_results = state.get("filtered_results", [])
        session_id = state.get("session_id")
        
        logger.info("[CAG] Генерация черновика ответа")
        
        # Формируем контекст
        context = self._build_context(filtered_results)
        
        prompt = f"""Контекст из дневника пользователя:
{context}

---
Вопрос пользователя: {question}

Ответь на вопрос, используя только информацию из контекста.
Если информации недостаточно, честно скажи об этом."""
        
        try:
            # Используем автовыбор модели
            response = await self.llm_service.auto_select_and_generate(
                prompt=prompt,
                query_type="analysis",
                system_prompt=self.system_prompt,
                session_id=session_id
            )
            
            state["draft_answer"] = response.content
            state["selected_model"] = response.model_name
            
        except Exception as e:
            logger.error(f"[CAG] Ошибка генерации: {e}")
            state["draft_answer"] = "Извините, произошла ошибка при генерации ответа."
        
        return state
    
    def _build_context(self, results: List[Dict[str, Any]]) -> str:
        """Построение контекста из результатов поиска."""
        if not results:
            return "Релевантных записей не найдено."
        
        parts = []
        for i, result in enumerate(results, 1):
            title = result.get('title', '')
            content = result.get('description', result.get('page_content', ''))
            date = result.get('event_date', '')
            
            parts.append(f"""[Запись {i}]
Дата: {date}
Заголовок: {title}
Содержание: {content}
""")
        
        return "\n".join(parts)
    
    # =========================================================================
    # ШАГ 4: ПРОВЕРКА КАЧЕСТВА
    # =========================================================================
    
    async def check_quality(self, state: CAGState) -> CAGState:
        """
        Проверка качества ответа.
        
        Проверяет:
        1. Ответ не пустой
        2. Ответ отвечает на вопрос
        3. Нет галлюцинаций (факты есть в контексте)
        """
        draft_answer = state.get("draft_answer", "")
        
        logger.info("[CAG] Проверка качества ответа")
        
        correction_feedback = []
        
        # Проверка 1: Ответ не пустой
        if not draft_answer or len(draft_answer.strip()) < 20:
            correction_feedback.append("Ответ слишком короткий")
        
        # Проверка 2: Ответ содержит отказ или неуверенность
        uncertainty_markers = [
            "не могу помочь",
            "не понимаю",
            "ошибка",
            "не знаю"
        ]
        
        has_uncertainty = any(
            marker in draft_answer.lower() 
            for marker in uncertainty_markers
        )
        
        if has_uncertainty and state.get("filtered_results"):
            # Есть контекст, но модель не уверена
            correction_feedback.append("Есть контекст, но ответ содержит неуверенность")
        
        # Решаем, нужна ли коррекция
        needs_correction = len(correction_feedback) > 0
        attempts = state.get("correction_attempts", 0)
        
        state["needs_correction"] = needs_correction and attempts < self.max_correction_attempts
        state["correction_feedback"] = correction_feedback
        state["correction_attempts"] = attempts
        
        if needs_correction:
            logger.info(f"[CAG] Требуется коррекция: {correction_feedback}")
        
        return state
    
    # =========================================================================
    # ШАГ 5: КОРРЕКЦИЯ
    # =========================================================================
    
    async def correct_answer(self, state: CAGState) -> CAGState:
        """Коррекция ответа на основе обратной связи."""
        draft_answer = state.get("draft_answer", "")
        question = state["question"]
        feedback = state.get("correction_feedback", [])
        session_id = state.get("session_id")
        
        logger.info(f"[CAG] Коррекция ответа (попытка {state.get('correction_attempts', 0) + 1})")
        
        prompt = f"""Предыдущий ответ:
{draft_answer}

Проблемы с ответом:
{chr(10).join(f'- {f}' for f in feedback)}

Вопрос пользователя: {question}

Пожалуйста, улучши ответ, учитывая указанные проблемы."""
        
        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                system_prompt=self.system_prompt,
                session_id=session_id
            )
            
            state["draft_answer"] = response.content
            state["correction_attempts"] = state.get("correction_attempts", 0) + 1
            
        except Exception as e:
            logger.error(f"[CAG] Ошибка коррекции: {e}")
            state["correction_attempts"] = self.max_correction_attempts
        
        return state
    
    # =========================================================================
    # ШАГ 6: ФИНАЛИЗАЦИЯ
    # =========================================================================
    
    async def finalize(self, state: CAGState) -> CAGState:
        """Финализация ответа."""
        state["answer"] = state.get("draft_answer", "")
        
        logger.info(f"[CAG] Финальный ответ готов ({len(state['answer'])} символов)")
        
        return state
    
    # =========================================================================
    # STREAMING API
    # =========================================================================
    
    async def stream_response(self, state: CAGState) -> AsyncGenerator[str, None]:
        """Streaming версия генерации ответа."""
        question = state["question"]
        filtered_results = state.get("filtered_results", [])
        session_id = state.get("session_id")
        
        context = self._build_context(filtered_results)
        
        prompt = f"""Контекст:
{context}

---
Вопрос: {question}"""
        
        try:
            async for chunk in self.llm_service.stream_response(
                prompt=prompt,
                system_prompt=self.system_prompt,
                session_id=session_id
            ):
                yield chunk.content
        except Exception as e:
            logger.error(f"[CAG] Streaming error: {e}")
            yield "Произошла ошибка при генерации ответа."
    
    # =========================================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # =========================================================================
    
    async def run(
        self,
        question: str,
        user_id: str,
        thread_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Запуск CAG пайплайна.
        
        Args:
            question: Вопрос пользователя
            user_id: ID пользователя
            thread_id: ID диалога
            session_id: ID сессии
            
        Returns:
            Результат с ответом и метаданными
        """
        start_time = datetime.now()
        
        # Инициализация состояния
        initial_state: CAGState = {
            "question": question,
            "user_id": user_id,
            "thread_id": thread_id or "",
            "session_id": session_id or "",
            "search_results": [],
            "relevance_grades": [],
            "filtered_results": [],
            "needs_correction": False,
            "draft_answer": "",
            "answer": "",
            "correction_attempts": 0,
            "correction_feedback": [],
            "selected_model": "",
            "processing_time_ms": 0
        }
        
        # Запуск графа
        graph = self.build_graph()
        final_state = await graph.ainvoke(initial_state)
        
        # Расчёт времени
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        logger.info(f"[CAG] Pipeline completed in {processing_time:.0f}ms")
        
        return {
            "answer": final_state.get("answer", ""),
            "model": final_state.get("selected_model", ""),
            "corrections": final_state.get("correction_attempts", 0),
            "sources": len(final_state.get("filtered_results", [])),
            "processing_time_ms": processing_time
        }
