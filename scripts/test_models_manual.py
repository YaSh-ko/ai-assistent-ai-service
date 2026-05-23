#!/usr/bin/env python
"""
Скрипт для ручного тестирования LLM моделей.
Позволяет интерактивно выбрать модель, настроить параметры и отправить запросы.
"""

import asyncio
import sys
import time
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.factory.model_factory import ModelFactory
from app.services.llm_service import LLMService
from app.monitoring.metrics import ModelMetrics


def print_header():
    """Вывод заголовка."""
    print("\n" + "=" * 60)
    print("       LLM Models Manual Testing Tool")
    print("=" * 60)


def print_menu():
    """Вывод главного меню."""
    print("\n--- Main Menu ---")
    print("1. List available models")
    print("2. Select model")
    print("3. Check model availability")
    print("4. Send test request")
    print("5. Test streaming")
    print("6. Change model parameters")
    print("7. View metrics")
    print("8. Compare all models")
    print("9. Exit")
    print("-" * 20)


def list_models():
    """Показать список доступных моделей."""
    print("\n📋 Available Models:")
    print("-" * 40)
    
    models_info = ModelFactory.get_models_info()
    current = ModelFactory.get_current_model()
    
    for i, model in enumerate(models_info, 1):
        status = "⭐" if model["name"] == current else "  "
        cached = "📦" if model["cached"] else "  "
        print(f"  {status} {i}. {model['name']:<15} {cached}")
        
        config = model.get("config", {})
        print(f"       Temperature: {config.get('temperature', 'N/A')}")
        print(f"       Max tokens: {config.get('max_tokens', 'N/A')}")
    
    print(f"\n  ⭐ = Current model, 📦 = Cached")


def select_model():
    """Интерактивный выбор модели."""
    models = ModelFactory.get_available_models()
    
    print("\n📌 Select Model:")
    for i, name in enumerate(models, 1):
        current = " (current)" if name == ModelFactory.get_current_model() else ""
        print(f"  {i}. {name}{current}")
    
    try:
        choice = input("\nEnter number (or model name): ").strip()
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                model_name = models[idx]
            else:
                print("❌ Invalid selection")
                return
        else:
            model_name = choice.lower()
        
        ModelFactory.set_current_model(model_name)
        print(f"✅ Selected model: {model_name}")
        
    except ValueError as e:
        print(f"❌ Error: {e}")


async def check_availability():
    """Проверка доступности всех моделей."""
    print("\n🔍 Checking model availability...")
    print("-" * 40)
    
    availability = await ModelFactory.check_availability()
    
    for name, available in availability.items():
        status = "✅ Available" if available else "❌ Unavailable"
        print(f"  {name:<20} {status}")


async def send_test_request():
    """Отправка тестового запроса."""
    current = ModelFactory.get_current_model()
    print(f"\n📤 Send test request to: {current}")
    
    prompt = input("Enter prompt (or press Enter for default): ").strip()
    if not prompt:
        prompt = "Привет! Расскажи кратко о себе."
    
    print(f"\n🔄 Sending request...")
    
    llm_service = LLMService()
    start_time = time.time()
    
    try:
        response = await llm_service.generate_response(prompt=prompt)
        
        elapsed = (time.time() - start_time) * 1000
        
        print("\n" + "=" * 50)
        print("📨 Response:")
        print("-" * 50)
        print(response.content)
        print("-" * 50)
        print(f"📊 Metrics:")
        print(f"   Model: {response.model_name}")
        print(f"   Tokens used: {response.tokens_used}")
        print(f"   Prompt tokens: {response.prompt_tokens}")
        print(f"   Completion tokens: {response.completion_tokens}")
        print(f"   Latency: {response.latency_ms:.2f} ms (total: {elapsed:.2f} ms)")
        print(f"   Finish reason: {response.finish_reason}")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_streaming():
    """Тестирование стриминга."""
    current = ModelFactory.get_current_model()
    print(f"\n🔄 Testing streaming with: {current}")
    
    prompt = input("Enter prompt (or press Enter for default): ").strip()
    if not prompt:
        prompt = "Расскажи короткую историю о космосе."
    
    print(f"\n🔄 Starting stream...")
    print("-" * 40)
    
    llm_service = LLMService()
    start_time = time.time()
    total_content = ""
    chunk_count = 0
    
    try:
        async for chunk in llm_service.stream_response(prompt=prompt):
            if chunk.content:
                print(chunk.content, end="", flush=True)
                total_content += chunk.content
                chunk_count += 1
            
            if chunk.is_final:
                break
        
        elapsed = (time.time() - start_time) * 1000
        
        print("\n" + "-" * 40)
        print(f"📊 Stream completed:")
        print(f"   Total chunks: {chunk_count}")
        print(f"   Total characters: {len(total_content)}")
        print(f"   Total time: {elapsed:.2f} ms")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")


def change_parameters():
    """Изменение параметров модели."""
    current = ModelFactory.get_current_model()
    provider = ModelFactory.get_model(current)
    config = provider.get_config()
    
    print(f"\n⚙️ Current parameters for {current}:")
    print(f"   Temperature: {config.temperature}")
    print(f"   Max tokens: {config.max_tokens}")
    print(f"   Top-p: {config.top_p}")
    
    print("\nEnter new values (press Enter to keep current):")
    
    try:
        temp = input(f"   Temperature [{config.temperature}]: ").strip()
        if temp:
            provider.set_parameters(temperature=float(temp))
        
        max_tok = input(f"   Max tokens [{config.max_tokens}]: ").strip()
        if max_tok:
            provider.set_parameters(max_tokens=int(max_tok))
        
        top_p = input(f"   Top-p [{config.top_p}]: ").strip()
        if top_p:
            provider.set_parameters(top_p=float(top_p))
        
        new_config = provider.get_config()
        print(f"\n✅ Updated parameters:")
        print(f"   Temperature: {new_config.temperature}")
        print(f"   Max tokens: {new_config.max_tokens}")
        print(f"   Top-p: {new_config.top_p}")
        
    except ValueError as e:
        print(f"❌ Error: {e}")


def view_metrics():
    """Просмотр метрик."""
    metrics = ModelMetrics()
    stats = metrics.get_all_stats()
    
    print("\n📊 Model Metrics:")
    print("-" * 60)
    
    if not stats:
        print("  No metrics recorded yet.")
        return
    
    for name, data in stats.items():
        print(f"\n  📌 {name}:")
        print(f"     Total requests: {data.get('total_requests', 0)}")
        print(f"     Success rate: {data.get('success_rate', 0):.1%}")
        print(f"     Avg latency: {data.get('avg_latency_ms', 0):.2f} ms")
        print(f"     Total tokens: {data.get('total_tokens', 0)}")


async def compare_all_models():
    """Сравнение всех моделей на одном запросе."""
    print("\n🔬 Comparing all models...")
    
    prompt = input("Enter prompt (or press Enter for default): ").strip()
    if not prompt:
        prompt = "Что такое искусственный интеллект? Ответь в одном предложении."
    
    print(f"\n📤 Prompt: {prompt}")
    print("=" * 60)
    
    llm_service = LLMService()
    models = ModelFactory.get_available_models()
    
    results = []
    
    for model_name in models:
        print(f"\n🔄 Testing {model_name}...")
        
        # Проверяем доступность
        provider = ModelFactory.get_model(model_name)
        if not await provider.is_available():
            print(f"   ❌ Model is not available")
            results.append({
                "model": model_name,
                "available": False
            })
            continue
        
        try:
            start = time.time()
            response = await llm_service.generate_response(
                prompt=prompt,
                model_name=model_name
            )
            elapsed = (time.time() - start) * 1000
            
            results.append({
                "model": model_name,
                "available": True,
                "latency_ms": response.latency_ms,
                "total_time_ms": elapsed,
                "tokens": response.tokens_used,
                "content": response.content[:100] + "..." if len(response.content) > 100 else response.content
            })
            
            print(f"   ✅ Response received in {elapsed:.2f} ms")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append({
                "model": model_name,
                "available": True,
                "error": str(e)
            })
    
    # Показываем результаты
    print("\n" + "=" * 60)
    print("📊 Comparison Results:")
    print("-" * 60)
    
    for r in results:
        print(f"\n📌 {r['model']}:")
        if not r.get("available"):
            print("   Status: ❌ Not available")
        elif r.get("error"):
            print(f"   Status: ❌ Error - {r['error']}")
        else:
            print(f"   ✅ Latency: {r['latency_ms']:.2f} ms")
            print(f"   ✅ Tokens: {r['tokens']}")
            print(f"   ✅ Response: {r['content']}")


async def main():
    """Главный цикл."""
    print_header()
    
    while True:
        print_menu()
        choice = input("Select option: ").strip()
        
        if choice == "1":
            list_models()
        elif choice == "2":
            select_model()
        elif choice == "3":
            await check_availability()
        elif choice == "4":
            await send_test_request()
        elif choice == "5":
            await test_streaming()
        elif choice == "6":
            change_parameters()
        elif choice == "7":
            view_metrics()
        elif choice == "8":
            await compare_all_models()
        elif choice == "9":
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid option. Please try again.")


if __name__ == "__main__":
    asyncio.run(main())
