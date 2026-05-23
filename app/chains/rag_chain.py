"""
RAG Chain - Полный пайплайн обработки запросов.

5 шагов:
1. ПОИСК (Hybrid Search: BM25 + Vector) → 10 результатов
2. ФИЛЬТРАЦИЯ (Reranker) → 3-5 результатов  
3. REASONING (Chain-of-Thought + Neo4j граф)
4. ГЕНЕРАЦИЯ (GigaChat Pro/Max со стримингом)
5. СОХРАНЕНИЕ (PostgreSQL + Neo4j + ChromaDB)
"""

from typing import Any, Dict, List, TypedDict, Optional, AsyncGenerator, Literal
from datetime import date, datetime
from enum import Enum
import asyncio

from langgraph.graph import StateGraph, END

from app.chains.base_chain import BaseChain
from app.data_access.repositories.dal import DataAccessLayer
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.reasoning_service import ReasoningService
from app.core.model_selector import ModelSelector
from app.core.complexity_classifier import get_complexity_classifier
from app.models.complexity_models import ComplexityLevel, QueryContext
from app.core.config import settings
from app.monitoring.logger import get_logger

logger = get_logger(__name__)


class RAGState(TypedDict):
    """Состояние RAG пайплайна."""
    # Входные данные
    question: str
    user_id: str
    thread_id: str
    session_id: str
    
    # Промежуточные результаты
    query_embedding: Optional[List[float]]
    search_results: List[Dict[str, Any]]  # ШАГ 1: 10 результатов
    filtered_results: List[Dict[str, Any]]  # ШАГ 2: 3-5 результатов
    context: str  # Контекст для LLM
    
    # Reasoning результаты
    reasoning_steps: List[Dict[str, Any]]  # ШАГ 3: Цепочка рассуждений
    reasoning_engine_used: str
    reasoning_metadata: Dict[str, Any]
    graph_insights: List[Dict[str, Any]]  # Инсайты из Neo4j
    
    # Выходные данные
    answer: str  # ШАГ 4: Финальный ответ
    extracted_events: List[Dict[str, Any]]  # ШАГ 5: События для сохранения
    
    # Метаданные
    complexity: str  # simple/medium/complex
    selected_model: str  # vllm/gigachat_pro/gigachat_max
    processing_time_ms: float


class RAGChain(BaseChain):
    """
    RAG Chain с 5-шаговым пайплайном.
    
    Поток обработки:
    1. retrieve_events → Hybrid Search (BM25 + Vector) → 10 результатов
    2. filter_relevant → Reranker → 3-5 результатов
    3. cot_reasoning → Chain-of-Thought + Neo4j анализ
    4. generate_response → GigaChat (выбор по сложности) + Streaming
    5. save_to_db → PostgreSQL + Neo4j + ChromaDB
    """
    
    def __init__(
        self,
        dal: DataAccessLayer,
        embedding_service: EmbeddingService,
        llm_service: Optional[LLMService] = None,
        reasoning_service: Optional[ReasoningService] = None,
        hybrid_search_provider: Optional[Any] = None,
        reranker_provider: Optional[Any] = None,
        graph_repository: Optional[Any] = None,
        pii_service: Optional[Any] = None
    ):
        self.dal = dal
        self.embedding_service = embedding_service
        self.llm_service = llm_service or LLMService()
        self.reasoning_service = reasoning_service or ReasoningService()
        self.hybrid_search_provider = hybrid_search_provider
        self.reranker_provider = reranker_provider
        self.graph_repository = graph_repository
        self.pii_service = pii_service
        self.complexity_classifier = get_complexity_classifier()
        
        # Конфигурация
        self.search_top_k = 10  # ШАГ 1: Количество результатов поиска
        self.rerank_top_k = 5   # ШАГ 2: Количество после фильтрации
        
        # Системный промпт для Delёz
        self.system_prompt = self._build_system_prompt()
    
    def _get_temperature_for_complexity(self, complexity: str) -> float:
        """Возвращает temperature на основе сложности запроса."""
        temps = {"simple": 0.3, "medium": 0.5, "complex": 0.7}
        return temps.get(complexity, 0.5)
    
    def _get_max_tokens_for_complexity(self, complexity: str) -> int:
        """Возвращает max_tokens на основе сложности запроса."""
        tokens = {"simple": 500, "medium": 1500, "complex": 2000}
        return tokens.get(complexity, 1500)
    
    def _build_system_prompt(self) -> str:
        """Построение системного промпта для личности Delёz."""
        return (
            "Ты - Delёz, умный и заботливый личный помощник для ведения дневника и самоанализа.\n\n"
            "Твоя задача - помогать пользователю:\n"
            "- Анализировать свои эмоции и события\n"
            "- Находить паттерны в записях\n"
            "- Давать мягкие рекомендации для саморазвития\n"
            "- Вести осмысленный диалог о жизни пользователя\n\n"
            "Правила:\n"
            "1. Будь эмпатичным и понимающим\n"
            "2. Задавай уточняющие вопросы когда нужно\n"
            "3. Ссылайся на прошлые записи пользователя когда это релевантно\n"
            "4. Показывай свой ход мыслей при анализе\n"
            "5. Не давай медицинских советов - рекомендуй специалистов при необходимости"
        )
    
    def build_graph(self) -> StateGraph:
        """Построение LangGraph графа."""
        workflow = StateGraph(RAGState)
        
        # Определение узлов
        workflow.add_node("classify_query", self.classify_query)
        workflow.add_node("retrieve_events", self.retrieve_events)
        workflow.add_node("filter_relevant", self.filter_relevant)
        workflow.add_node("cot_reasoning", self.cot_reasoning)
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("save_to_db", self.save_to_db)
        
        # Определение связей
        workflow.set_entry_point("classify_query")
        workflow.add_edge("classify_query", "retrieve_events")
        workflow.add_edge("retrieve_events", "filter_relevant")
        
        # Conditional routing based on complexity
        workflow.add_conditional_edges(
            "filter_relevant",
            self._route_based_on_complexity,
            {
                "simple": "generate_response",
                "complex": "cot_reasoning"
            }
        )
        
        workflow.add_edge("cot_reasoning", "generate_response")
        workflow.add_edge("generate_response", "save_to_db")
        workflow.add_edge("save_to_db", END)
        
        return workflow.compile()

    def _route_based_on_complexity(self, state: RAGState) -> Literal["simple", "complex"]:
        """Маршрутизация на основе сложности."""
        complexity = state.get("complexity", "simple")
        if complexity == "simple":
            return "simple"
        return "complex"
    
    # =========================================================================
    # ШАГ 0: КЛАССИФИКАЦИЯ ЗАПРОСА
    # =========================================================================
    
    async def classify_query(self, state: RAGState) -> RAGState:
        """
        Классификация сложности запроса для выбора модели.
        
        SIMPLE → vLLM (локально)
        MEDIUM → GigaChat Pro
        COMPLEX → GigaChat Max
        """
        
        question = state["question"]
        context = QueryContext(
            thread_id=state.get("thread_id"),
            user_id=state.get("user_id")
        )
        
        # Классифицируем запрос
        complexity_result = self.complexity_classifier.classify(question, context)
        
        logger.info(
            f"Query classified as {complexity_result.level.value} "
            f"(confidence: {complexity_result.confidence:.2f}) → {complexity_result.suggested_model}"
        )
        
        state["complexity"] = complexity_result.level.value
        state["selected_model"] = complexity_result.suggested_model
        
        return state
    
    # =========================================================================
    # ШАГ 1: ПОИСК ПОХОЖИХ СОБЫТИЙ (RAG)
    # =========================================================================
    
    async def retrieve_events(self, state: RAGState) -> RAGState:
        """
        Hybrid Search: BM25 (полнотекстовый) + Vector Search (GigaChat Embeddings) + Graph Search.
        
        Возвращает топ-10 похожих событий из истории пользователя.
        """
        question = state["question"]
        user_id = state.get("user_id")
        
        logger.info(f"[ШАГ 1] Поиск событий для: '{question[:50]}...'")
        
        try:
            # Генерируем embedding для запроса
            if self.embedding_service:
                query_embedding = await self.embedding_service.generate_embedding(question)
                state["query_embedding"] = query_embedding
            else:
                query_embedding = [0.0] * 1024  # Заглушка
                state["query_embedding"] = query_embedding
            
            # Extract concepts from question for graph search
            # Simple: split question into words, filter stopwords, use as concepts
            query_concepts = [w.lower() for w in question.split() if len(w) > 3][:5]
            
            # Run searches in parallel
            search_tasks = []
            
            # Hybrid (BM25 + Vector)
            if self.hybrid_search_provider:
                search_tasks.append(
                    self.hybrid_search_provider.search(
                        query=question,
                        query_embedding=query_embedding,
                        top_k=self.search_top_k,
                        user_id=user_id
                    )
                )
            else:
                search_tasks.append(
                    self._fallback_search(query_embedding, user_id)
                )
            
            # Graph search (if available)
            if self.graph_repository:
                search_tasks.append(
                    self.graph_repository.graph_search(
                        user_id=user_id,
                        query_concepts=query_concepts,
                        limit=self.search_top_k
                    )
                )
            else:
                search_tasks.append(self._get_empty_list_async())
            
            # Execute all searches in parallel
            results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            hybrid_results = results[0] if not isinstance(results[0], Exception) else []
            graph_results = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else []
            
            if isinstance(results[0], Exception):
                logger.warning(f"Hybrid search failed: {results[0]}")
            if len(results) > 1 and isinstance(results[1], Exception):
                logger.warning(f"Graph search failed: {results[1]}")
            
            # Merge results (deduplicate by id)
            merged = {}
            for r in hybrid_results:
                doc_id = str(r.get('id', ''))
                if doc_id:
                    merged[doc_id] = r
            
            for r in graph_results:
                doc_id = str(r.get('id', ''))
                if doc_id and doc_id not in merged:
                    merged[doc_id] = r
                elif doc_id and doc_id in merged:
                    # Combine scores
                    merged[doc_id]['graph_score'] = r.get('graph_score', 0)
                    merged[doc_id]['matched_concepts'] = r.get('matched_concepts', [])
            
            # Sort by combined score
            search_results = list(merged.values())
            search_results.sort(
                key=lambda x: (x.get('final_score', 0) + x.get('graph_score', 0) * 0.3), 
                reverse=True
            )
            
            state["search_results"] = search_results[:self.search_top_k]
            state["graph_insights"] = [{"type": "graph_search", "concepts": query_concepts}]
            
            logger.info(f"[ШАГ 1] Найдено {len(state['search_results'])} событий (hybrid: {len(hybrid_results)}, graph: {len(graph_results)})")
            
        except Exception as e:
            logger.error(f"[ШАГ 1] Ошибка поиска: {e}")
            state["search_results"] = []
        
        return state

    def _get_empty_list(self) -> List[Any]:
        """Вспомогательный метод для возврата пустого списка в asyncio.gather."""
        return []
    
    async def _get_empty_list_async(self) -> List[Any]:
        """Async вспомогательный метод для возврата пустого списка в asyncio.gather."""
        return []
    
    async def _fallback_search(
        self,
        query_embedding: List[float], 
        user_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Fallback поиск через embedding repository."""
        try:
            if hasattr(self.dal, 'embedding_repo'):
                results = await self.dal.embedding_repo.search_similar(
                    query_embedding=query_embedding,
                    top_k=self.search_top_k,
                    user_id=user_id
                )
                return results
        except Exception as e:
            logger.warning(f"Fallback search failed: {e}")
        return []
    
    # =========================================================================
    # ШАГ 2: ФИЛЬТРАЦИЯ (CAG - Corrective RAG)
    # =========================================================================
    
    async def filter_relevant(self, state: RAGState) -> RAGState:
        """
        Reranker: сортировка по релевантности, оставляет 3-5 лучших.
        
        Убирает шум, экономит токены для LLM.
        """
        search_results = state.get("search_results", [])
        question = state["question"]
        
        logger.info(f"[ШАГ 2] Фильтрация {len(search_results)} результатов")
        
        if not search_results:
            state["filtered_results"] = []
            state["context"] = ""
            return state
        
        try:
            if self.reranker_provider:
                # Используем reranker для переранжирования
                filtered_results = await self.reranker_provider.rerank(
                    query=question,
                    documents=search_results,
                    top_k=self.rerank_top_k
                )
            else:
                # Fallback: берём топ по final_score
                sorted_results = sorted(
                    search_results, 
                    key=lambda x: x.get('final_score', x.get('score', 0)), 
                    reverse=True
                )
                filtered_results = sorted_results[:self.rerank_top_k]
            
            state["filtered_results"] = filtered_results
            
            # Формируем контекст для LLM
            context = self._build_context_from_results(filtered_results)
            state["context"] = context
            
            logger.info(f"[ШАГ 2] Отфильтровано до {len(filtered_results)} релевантных событий")
            
        except Exception as e:
            logger.error(f"[ШАГ 2] Ошибка фильтрации: {e}")
            state["filtered_results"] = search_results[:self.rerank_top_k]
            state["context"] = self._build_context_from_results(state["filtered_results"])
        
        return state
    
    def _build_context_from_results(self, results: List[Dict[str, Any]]) -> str:
        """Построение контекста из результатов поиска."""
        if not results:
            return ""
        
        context_parts = ["Релевантные записи из дневника пользователя:\n"]
        
        for i, result in enumerate(results, 1):
            title = result.get('title', '')
            description = result.get('description', result.get('page_content', ''))
            event_date = result.get('event_date', '')
            score = result.get('final_score', result.get('score', 0))
            
            context_parts.append(f"""
--- Запись {i} (релевантность: {score:.2f}) ---
Дата: {event_date}
Заголовок: {title}
Содержание: {description}
""")
        
        return "\n".join(context_parts)
    
    # =========================================================================
    # ШАГ 3: REASONING (Chain-of-Thought)
    # =========================================================================
    
    async def cot_reasoning(self, state: RAGState) -> RAGState:
        """
        Chain-of-Thought reasoning:
        Использует ReasoningService для выполнения глубокого анализа.
        """
        question = state["question"]
        filtered_results = state.get("filtered_results", [])
        user_id = state.get("user_id")
        complexity = state.get("complexity", "simple")
        
        logger.info(f"[ШАГ 3] CoT Reasoning для: '{question[:50]}...' (complexity: {complexity})")
        
        try:
            # Подготовка контекста для reasoning
            context = {
                "rag_results": filtered_results,
                "user_id": user_id,
                "thread_id": state.get("thread_id")
            }
            
            # Выполнение reasoning через сервис
            result = await self.reasoning_service.execute_reasoning(
                question=question,
                context=context,
                task_type=complexity, # Используем сложность как тип задачи
                user_id=user_id
            )
            
            # Обновление состояния
            state["reasoning_steps"] = result.get("steps", [])
            state["reasoning_engine_used"] = result.get("metadata", {}).get("type", "unknown")
            state["reasoning_metadata"] = result.get("metadata", {})
            
            # Если есть ответ от reasoning (например, финальный), можно его использовать
            # Но обычно мы передаем шаги в generate_response для финальной генерации в нужном стиле
            
            logger.info(f"[ШАГ 3] Завершено: {len(state['reasoning_steps'])} шагов рассуждения")
            
        except Exception as e:
            logger.error(f"[ШАГ 3] Ошибка CoT Reasoning: {e}")
            state["reasoning_steps"] = []
            state["reasoning_engine_used"] = "failed"
            state["reasoning_metadata"] = {"error": str(e)}
        
        return state
    
    async def _analyze_graph_connections(
        self,
        filtered_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Анализ связей через Neo4j граф."""
        insights = []
        
        if not self.graph_repository:
            return insights
        
        try:
            # Получаем связанные концепты и аффекты
            for result in filtered_results[:3]:  # Анализируем топ-3
                entry_id = result.get('id') or result.get('metadata', {}).get('entry_id')
                
                if entry_id:
                    # Поиск связанных узлов
                    related = await self.graph_repository.find_related_nodes(
                        node_id=entry_id,
                        relationship_types=["RELATES_TO", "CAUSES", "AFFECTS"]
                    )
                    
                    if related:
                        insights.append({
                            "entry_id": entry_id,
                            "related_nodes": related[:5]
                        })
        except Exception as e:
            logger.warning(f"Graph analysis error: {e}")
        
        return insights
    
    # =========================================================================
    # ШАГ 4: ГЕНЕРАЦИЯ ОТВЕТА
    # =========================================================================
    
    # =========================================================================
    # ШАГ 4: ГЕНЕРАЦИЯ ОТВЕТА
    # =========================================================================
    
    async def generate_response(self, state: RAGState) -> RAGState:
        """
        Генерация ответа с GigaChat (Pro/Max).
        
        Формат сообщений:
        - System: Личность Delёz
        - Assistant: История диалога (если есть)
        - User: Контекст RAG + текущий вопрос
        
        Использует:
        - Выбор модели по сложности
        - thread_id для кэширования
        - Streaming для живого отклика
        """
        from app.core.model_selector import ModelSelector
        
        question = state["question"]
        context = state.get("context", "")
        thread_id = state.get("thread_id")
        complexity = state.get("complexity", "simple")
        reasoning_steps = state.get("reasoning_steps", [])
        
        # Select model and params
        selected_model = ModelSelector.select_model(complexity)
        params = ModelSelector.get_params(complexity)
        
        state["selected_model"] = selected_model
        logger.info(f"[ШАГ 4] Генерация ответа с {selected_model} (params: {params})")
        
        # Fetch history (last 5 messages)
        history = []
        if thread_id and hasattr(self.dal, 'chat_session_repo'):
            try:
                history = await self.dal.chat_session_repo.get_history(thread_id, limit=5)
            except Exception as e:
                logger.warning(f"Failed to fetch history: {e}")
        
        # Формируем промпт с контекстом
        full_prompt = self._build_full_prompt(question, context, reasoning_steps, history)
        
        # System prompt (Deleuze persona)
        system_prompt = (
            "Ты философ Gilles Deleuze, анализирующий события жизни через призму "
            "аффекта, ризомы и становления. Твой стиль: глубокий, практический, "
            "связывающий микро-события с макро-паттернами."
        )
        
        try:
            # Генерация ответа
            response = await self.llm_service.generate_response(
                prompt=full_prompt,
                model_name=selected_model,
                system_prompt=system_prompt,
                session_id=thread_id,
                temperature=params["temperature"],
                max_tokens=params["max_tokens"],
                top_p=params["top_p"]
            )
            
            state["answer"] = response.content
            logger.info(f"[ШАГ 4] Ответ сгенерирован ({len(response.content)} символов)")
            
        except Exception as e:
            logger.error(f"[ШАГ 4] Ошибка генерации: {e}")
            state["answer"] = "Извините, произошла ошибка при генерации ответа. Попробуйте переформулировать вопрос."
        
        return state
    
    def _build_full_prompt(
        self, 
        question: str, 
        context: str, 
        reasoning_steps: List[Dict],
        history: List[Dict] = None
    ) -> str:
        """Построение полного промпта с контекстом."""
        prompt_parts = []
        
        # Добавляем историю диалога
        if history:
            prompt_parts.append("ИСТОРИЯ ДИАЛОГА (сессия):")
            for msg in history:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                prompt_parts.append(f"{role.capitalize()}: {content}")
            prompt_parts.append("\n─────────────────────────────────────────\n")
        
        # Добавляем контекст из RAG
        if context:
            prompt_parts.append("RAG КОНТЕКСТ (события из истории):")
            prompt_parts.append(context)
            prompt_parts.append("\n─────────────────────────────────────────\n")
        
        # Добавляем инсайты из рассуждений (для сложных запросов)
        if reasoning_steps:
            prompt_parts.append("REASONING КОНТЕКСТ:")
            prompt_parts.append("Вот цепочка рассуждений:")
            # Limit to top 5 steps to save tokens
            for step in reasoning_steps[:5]:
                desc = step.get('description', '')
                thought = step.get('thought', '')
                obs = step.get('observation', '')
                prompt_parts.append(f"- Шаг {step.get('step_number', '?')}: {desc}")
                if thought:
                    prompt_parts.append(f"  Мысль: {thought}")
                if obs:
                    prompt_parts.append(f"  Результат: {obs}")
            prompt_parts.append("\n─────────────────────────────────────────\n")
        
        # Добавляем вопрос пользователя
        prompt_parts.append("USER (текущий вопрос):")
        prompt_parts.append(f"\"{question}\"")
        
        return "\n".join(prompt_parts)
    
    # =========================================================================
    # ШАГ 5: СОХРАНЕНИЕ
    # =========================================================================
    
    async def save_to_db(self, state: RAGState) -> RAGState:
        """
        Сохранение результатов:
        - PostgreSQL: Диалог + новые выводы
        - Neo4j: Связи событие→вывод→концепт
        - ChromaDB: Embeddings для будущего поиска
        
        Применяет PII sanitization перед сохранением.
        """
        extracted_events = state.get("extracted_events", [])
        answer = state.get("answer", "")
        user_id = state.get("user_id")
        thread_id = state.get("thread_id")
        
        logger.info("[ШАГ 5] Сохранение результатов")
        
        # Anonymize answer if PII service is available
        if self.pii_service and answer:
            state["answer"] = self.pii_service.anonymize_text(answer)
        
        # Сохраняем извлечённые события
        if extracted_events:
            await self._save_extracted_events(extracted_events, user_id, thread_id)
        
        # Сохраняем связи в Neo4j (если есть граф-инсайты)
        if self.graph_repository and state.get("graph_insights"):
            try:
                await self._save_graph_insights(state)
            except Exception as e:
                logger.warning(f"[ШАГ 5] Ошибка сохранения в Neo4j: {e}")
        
        logger.info("[ШАГ 5] Сохранение завершено")

        # LLM quality evaluation (async, non-blocking)
        if settings.LLM_EVAL_ENABLED:
            try:
                from app.monitoring.llm_evaluator import RAGTrace, get_evaluator
                trace = RAGTrace(
                    question=state.get("question", ""),
                    context=[
                        r.get("description", r.get("page_content", ""))
                        for r in state.get("filtered_results", [])
                    ],
                    answer=state.get("answer", ""),
                    model=state.get("selected_model", "unknown"),
                    prompt_type=state.get("complexity", "simple"),
                    retriever="hybrid",
                    dataset=settings.LLM_EVAL_DATASET,
                    env=settings.LLM_EVAL_ENV,
                    version=settings.LLM_EVAL_VERSION,
                )
                get_evaluator().schedule(trace)
            except Exception as e:
                logger.warning(f"LLM eval scheduling failed: {e}")

        return state

    async def _save_extracted_events(self, events: List[Dict[str, Any]], user_id: str, thread_id: str) -> None:
        """Вспомогательный метод для сохранения извлеченных событий."""
        for event in events:
            try:
                # Anonymize event data
                if self.pii_service:
                    event = self.pii_service.anonymize_structure(event)
                    
                event_date = self._parse_event_date(event.get("event_date"))

                await self.dal.save_entry_with_embedding(
                    user_id=user_id,
                    title=event.get("title", ""),
                    description=event.get("description", ""),
                    event_date=event_date,
                    thread_id=thread_id
                )
                logger.debug(f"[ШАГ 5] Сохранено событие: {event.get('title', '')[:30]}")
            except Exception as e:
                logger.error(f"[ШАГ 5] Ошибка сохранения события: {e}")

    def _parse_event_date(self, date_val: Any) -> date:
        """Парсинг даты события из различных форматов."""
        if not date_val:
            return date.today()
            
        if isinstance(date_val, date):
            return date_val
            
        if isinstance(date_val, datetime):
            return date_val.date()
            
        if isinstance(date_val, str):
            return self._parse_date_string(date_val)
                    
        return date.today()

    def _parse_date_string(self, date_str: str) -> date:
        """Вспомогательный метод для парсинга строки даты."""
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        except ValueError:
            for fmt in ["%Y-%m-%d", "%d.%m.%Y"]:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
        return date.today()
    
    async def _save_graph_insights(self, state: RAGState) -> None:
        """Сохранение инсайтов в Neo4j граф."""
        # Создаём узел для текущего анализа
        analysis_data = {
            "question": state.get("question", ""),
            "answer_summary": state.get("answer", "")[:200],
            "complexity": state.get("complexity", ""),
            "timestamp": datetime.now().isoformat()
        }
        
        # Связываем с релевантными записями
        for result in state.get("filtered_results", [])[:3]:
            entry_id = result.get('id') or result.get('metadata', {}).get('entry_id')
            if entry_id:
                await self.graph_repository.create_relationship(
                    from_id=entry_id,
                    to_data=analysis_data,
                    relationship_type="ANALYZED_IN"
                )
    
    # =========================================================================
    # STREAMING API
    # =========================================================================
    
    async def stream_response(self, state: RAGState) -> AsyncGenerator[str, None]:
        """
        Streaming версия генерации ответа.
        
        Yields:
            Токены ответа по мере генерации
        """
        question = state["question"]
        context = state.get("context", "")
        session_id = state.get("session_id")
        selected_model = state.get("selected_model", "gigachat")
        reasoning_steps = state.get("reasoning_steps", [])
        
        full_prompt = self._build_full_prompt(question, context, reasoning_steps)
        
        try:
            async for chunk in self.llm_service.stream_response(
                prompt=full_prompt,
                model_name=selected_model,
                system_prompt=self.system_prompt,
                session_id=session_id,
                temperature=self._get_temperature_for_complexity(state.get("complexity")),
                max_tokens=self._get_max_tokens_for_complexity(state.get("complexity"))
            ):
                yield chunk.content
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield "Извините, произошла ошибка при генерации ответа."
    
    # =========================================================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # =========================================================================
    
    async def process_user_message(
        self,
        thread_id: str,
        user_question: str,
        user_id: str,
    ) -> tuple[AsyncGenerator[Any, None], Dict[str, Any]]:
        """
        Оркестратор обработки сообщения пользователя (5 этапов).
        Поддерживает стриминг шагов рассуждения и финального ответа.
        
        Returns:
            (llm_stream, state)
        """
        from app.interfaces.model_provider import StreamChunk
        
        start_time = datetime.now()
        
        # Инициализация состояния
        state: RAGState = {
            "question": user_question,
            "user_id": user_id,
            "thread_id": thread_id,
            "session_id": thread_id, # Keep session_id for compatibility if needed internally
            "query_embedding": None,
            "search_results": [],
            "filtered_results": [],
            "context": "",
            "reasoning_steps": [],
            "reasoning_engine_used": "",
            "reasoning_metadata": {},
            "graph_insights": [],
            "answer": "",
            "extracted_events": [],
            "complexity": "simple", # Default
            "selected_model": "gigachat",
            "processing_time_ms": 0
        }
        
        try:
            # ШАГ 0: Классификация
            state = await self.classify_query(state)
            
            # ШАГ 1: Поиск (RAG)
            state = await self.retrieve_events(state)
            
            # ШАГ 2: Фильтрация (CAG)
            state = await self.filter_relevant(state)
            
            # ШАГ 3: Reasoning (CoT) - если нужно
            if state["complexity"] == "complex":
                state = await self.cot_reasoning(state)
            
            # ШАГ 4: Генерация (Streaming)
            
            # Fetch history (last 5 messages)
            history = []
            if thread_id and hasattr(self.dal, 'chat_session_repo'):
                try:
                    history = await self.dal.chat_session_repo.get_history(thread_id, limit=5)
                except Exception as e:
                    logger.warning(f"Failed to fetch history: {e}")

            # Подготовка промпта
            full_prompt = self._build_full_prompt(
                state["question"], 
                state.get("context", ""), 
                state.get("reasoning_steps", []),
                history
            )
            
            # Get params for model
            from app.core.model_selector import ModelSelector
            params = ModelSelector.get_params(state.get("complexity", "simple"))
            
            # Создаем генератор для LLM
            llm_stream = self.llm_service.stream_response(
                prompt=full_prompt,
                model_name=state.get("selected_model", "gigachat"),
                system_prompt=self.system_prompt,
                session_id=thread_id,
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 1024)
            )
            
            # Обертка для сохранения после стрима
            async def wrapped_stream():
                full_answer = ""
                async for chunk in llm_stream:
                    if chunk.content:
                        full_answer += chunk.content
                    yield chunk
                
                # ШАГ 5: Сохранение (после завершения стрима)
                state["answer"] = full_answer
                state["processing_time_ms"] = (datetime.now() - start_time).total_seconds() * 1000
                await self.save_to_db(state)

                # Сохраняем диалог в историю сессии
                if thread_id and hasattr(self.dal, 'chat_session_repo'):
                    try:
                        # Убеждаемся что сессия существует (upsert)
                        existing = await self.dal.chat_session_repo.get_by_id(thread_id)
                        if not existing:
                            await self.dal.chat_session_repo.create(user_id, thread_id)

                        await self.dal.chat_session_repo.add_message(
                            thread_id, {"role": "user", "content": user_question}
                        )
                        await self.dal.chat_session_repo.add_message(
                            thread_id, {"role": "assistant", "content": full_answer}
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save messages to history: {e}")
            
            return wrapped_stream(), state

        except Exception as e:
            logger.error(f"Error in process_user_message: {e}")
            # Return empty stream and state in case of error
            async def empty_stream():
                for _ in ():
                    yield None
                return
            return empty_stream(), state
