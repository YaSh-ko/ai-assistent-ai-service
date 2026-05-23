#!/usr/bin/env python3
"""
Демонстрация потоковой генерации ответа с реальным CoT в реальном времени.

Этот скрипт демонстрирует SSE стриминг с реальными ответами от GigaChat,
показывая шаги рассуждения Chain-of-Thought и токены по мере их получения.

Запуск: python3 scripts/demo_streaming.py
"""

import asyncio
import sys
import os
import time

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Загружаем переменные окружения (override чтобы .env имел приоритет)
from dotenv import load_dotenv
load_dotenv(override=True)


# Цвета для вывода в терминал
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def print_header():
    """Вывод заголовка демо."""
    print(f"\n{Colors.HEADER}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  Демонстрация CoT + Streaming - Реальное рассуждение{Colors.END}")
    print(f"{Colors.HEADER}{'='*60}{Colors.END}\n")


async def run_demo():
    """Запуск демонстрации с реальным CoT и GigaChat."""
    print_header()
    
    # Импортируем модули
    from app.providers.models.gigachat_provider import GigaChatProvider
    from app.providers.reasoning.cot_provider import CoTProvider
    from app.core.config import settings
    
    # Проверяем наличие credentials
    if not settings.GIGACHAT_CREDENTIALS and not (settings.GIGACHAT_CLIENT_ID and settings.GIGACHAT_CLIENT_SECRET):
        print(f"{Colors.RED}Ошибка: Не найдены GIGACHAT_CREDENTIALS или GIGACHAT_CLIENT_ID/SECRET{Colors.END}")
        print(f"{Colors.DIM}Установите переменные окружения в .env файле{Colors.END}")
        return
    
    # Создаём провайдер GigaChat
    gigachat = GigaChatProvider(version="base")
    
    # Создаём CoT провайдер
    cot_provider = CoTProvider(
        model_provider=gigachat,
        config={
            "max_reasoning_depth": 4,
            "enable_verification": True,
            "timeout_per_step": 60
        }
    )
    
    # Вопрос для демонстрации
    question = "Объясни концепцию 'различия' Делёза простыми словами."
    
    # Контекст для CoT (имитируем результаты поиска)
    context = {
        "search_results": [
            {"content": "Делёз рассматривает различие как первичную онтологическую категорию."},
            {"content": "Для Делёза различие не противопоставление, а процесс становления."}
        ],
        "user_history": []
    }
    
    print(f"{Colors.BOLD}Вопрос:{Colors.END} {question}\n")
    print(f"{Colors.DIM}{'─'*60}{Colors.END}\n")
    
    # Показываем "думание"
    print(f"{Colors.YELLOW}⏳ Запускаю Chain-of-Thought рассуждение...{Colors.END}\n")
    
    try:
        # Выполняем CoT рассуждение
        start_time = time.time()
        result = await cot_provider.reason(question, context)
        total_time = (time.time() - start_time) * 1000
        
        # Получаем шаги рассуждения
        reasoning_steps = cot_provider.get_reasoning_steps()
        
        # Показываем шаги рассуждения
        for step in reasoning_steps:
            step_num = step.get("step_number", "?")
            description = step.get("description", "")
            thought = step.get("thought", "")
            duration = step.get("duration_ms", 0)
            status = step.get("status", "")
            
            status_icon = "✓" if str(status) == "ReasoningStatus.COMPLETED" else "⏳"
            
            print(f"{Colors.BLUE}┌─ Шаг {step_num}: {description} {status_icon}{Colors.END}")
            print(f"{Colors.DIM}│  💭 {thought}{Colors.END}")
            if duration > 0:
                print(f"{Colors.DIM}│  ⏱️  {duration:.0f}мс{Colors.END}")
            print(f"{Colors.BLUE}└{'─'*50}{Colors.END}\n")
            await asyncio.sleep(0.2)
        
        print(f"\n{Colors.BOLD}{Colors.GREEN}Финальный ответ:{Colors.END}")
        print(f"{Colors.DIM}{'─'*60}{Colors.END}\n")
        
        # Печатаем финальный ответ с эффектом печатной машинки
        final_answer = result.final_answer if hasattr(result, 'final_answer') else str(result)
        for char in final_answer:
            print(char, end='', flush=True)
            await asyncio.sleep(0.01)
        
        print(f"\n\n{Colors.DIM}{'─'*60}{Colors.END}")
        print(f"{Colors.GREEN}✓ Рассуждение завершено за {total_time:.0f}мс{Colors.END}")
        
        # Показываем метаданные
        metadata = cot_provider.get_metadata()
        print(f"{Colors.DIM}  Шагов: {len(reasoning_steps)} | Модель: {metadata.get('type', 'N/A')}{Colors.END}\n")
        
    except Exception as e:
        print(f"\n{Colors.RED}Ошибка: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Закрываем сессию
        await gigachat.close()


if __name__ == "__main__":
    print("\033c", end="")  # Очистка терминала
    asyncio.run(run_demo())
