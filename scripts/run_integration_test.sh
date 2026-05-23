#!/bin/bash

# Скрипт для запуска финальной интеграционной проверки
# Python AI Service - Full Scenario Test

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "======================================================================"
echo "ФИНАЛЬНАЯ ИНТЕГРАЦИОННАЯ ПРОВЕРКА"
echo "Python AI Service - Full Scenario Test"
echo "======================================================================"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функции для вывода
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Параметры
API_URL="${1:-http://localhost:8001}"
PORT="${2:-8001}"

echo "Параметры:"
echo "  API URL: $API_URL"
echo "  Port: $PORT"
echo ""

# ========================================================================
# Шаг 1: Проверка зависимостей
# ========================================================================

echo "Шаг 1: Проверка зависимостей"
echo "----------------------------------------------------------------------"

# Проверить Python
if ! command -v python3 &> /dev/null; then
    print_error "Python3 не установлен"
    exit 1
fi
print_success "Python3 установлен"

# Проверить виртуальное окружение
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    print_info "Виртуальное окружение не найдено, создаем..."
    cd "$PROJECT_ROOT"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    print_success "Виртуальное окружение найдено"
fi

# Активировать виртуальное окружение
source "$PROJECT_ROOT/.venv/bin/activate"

# Проверить .env файл
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    print_error ".env файл не найден"
    print_info "Создайте .env файл на основе .env.example"
    exit 1
fi
print_success ".env файл найден"

echo ""

# ========================================================================
# Шаг 2: Проверка сервиса
# ========================================================================

echo "Шаг 2: Проверка сервиса"
echo "----------------------------------------------------------------------"

# Проверить доступность API
print_info "Проверка доступности API на $API_URL..."

if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
    print_success "API доступен"
    SERVICE_RUNNING=true
else
    print_info "API недоступен, попытка запуска..."
    SERVICE_RUNNING=false
fi

# Если сервис не запущен, попробовать запустить
if [ "$SERVICE_RUNNING" = false ]; then
    print_info "Запуск сервиса на порту $PORT..."
    
    # Проверить что порт свободен
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_error "Порт $PORT уже занят"
        print_info "Освободите порт или используйте другой: ./run_integration_test.sh http://localhost:XXXX XXXX"
        exit 1
    fi
    
    # Запустить сервис в фоне
    cd "$PROJECT_ROOT"
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT > /tmp/python-ai-service.log 2>&1 &
    SERVICE_PID=$!
    
    print_info "Сервис запущен (PID: $SERVICE_PID)"
    print_info "Ожидание запуска сервиса (30 секунд)..."
    
    # Ждать пока сервис запустится
    for i in {1..30}; do
        if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
            print_success "Сервис запущен и доступен"
            SERVICE_RUNNING=true
            break
        fi
        sleep 1
        echo -n "."
    done
    echo ""
    
    if [ "$SERVICE_RUNNING" = false ]; then
        print_error "Не удалось запустить сервис"
        print_info "Проверьте логи: tail -f /tmp/python-ai-service.log"
        exit 1
    fi
fi

echo ""

# ========================================================================
# Шаг 3: Проверка баз данных
# ========================================================================

echo "Шаг 3: Проверка баз данных"
echo "----------------------------------------------------------------------"

# Проверить PostgreSQL
print_info "Проверка PostgreSQL..."
if pg_isready -h localhost -p 5433 > /dev/null 2>&1; then
    print_success "PostgreSQL доступен"
else
    print_info "PostgreSQL недоступен (может быть не настроен)"
fi

# Проверить Neo4j
print_info "Проверка Neo4j..."
if curl -s -f http://localhost:7474 > /dev/null 2>&1; then
    print_success "Neo4j доступен"
else
    print_info "Neo4j недоступен (может быть не настроен)"
fi

# Проверить ChromaDB
print_info "Проверка ChromaDB..."
CHROMA_HOST=$(grep CHROMA_SERVER_HOST "$PROJECT_ROOT/.env" | cut -d '=' -f2)
CHROMA_PORT=$(grep CHROMA_SERVER_PORT "$PROJECT_ROOT/.env" | cut -d '=' -f2)

if [ -n "$CHROMA_HOST" ] && [ -n "$CHROMA_PORT" ]; then
    if curl -s -f "http://${CHROMA_HOST}:${CHROMA_PORT}/api/v1/heartbeat" > /dev/null 2>&1; then
        print_success "ChromaDB доступен"
    else
        print_info "ChromaDB недоступен (может быть не настроен)"
    fi
else
    print_info "ChromaDB не настроен в .env"
fi

echo ""

# ========================================================================
# Шаг 4: Запуск интеграционного теста
# ========================================================================

echo "Шаг 4: Запуск интеграционного теста"
echo "----------------------------------------------------------------------"

print_info "Запуск теста..."
echo ""

# Запустить тест
cd "$PROJECT_ROOT"
python3 "$SCRIPT_DIR/integration_test_full_scenario.py" "$API_URL"

TEST_EXIT_CODE=$?

echo ""

# ========================================================================
# Шаг 5: Cleanup
# ========================================================================

echo "Шаг 5: Cleanup"
echo "----------------------------------------------------------------------"

# Если мы запустили сервис, остановить его
if [ -n "$SERVICE_PID" ]; then
    print_info "Остановка сервиса (PID: $SERVICE_PID)..."
    kill $SERVICE_PID 2>/dev/null || true
    print_success "Сервис остановлен"
fi

echo ""

# ========================================================================
# Итоговый результат
# ========================================================================

echo "======================================================================"
if [ $TEST_EXIT_CODE -eq 0 ]; then
    print_success "ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!"
    echo "======================================================================"
    exit 0
else
    print_error "НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ"
    echo "======================================================================"
    print_info "Проверьте логи для деталей"
    exit 1
fi
