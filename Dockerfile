# Многоэтапная сборка для оптимизации размера образа
FROM python:3.11-slim AS base

RUN addgroup --system nonroot && adduser --system --ingroup nonroot nonroot && \
  apt-get update && apt-get install -y \
  curl \
  gcc \
  g++ \
  make \
  libpq-dev \
  ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Российские корневые сертификаты для GigaChat / Sberbank API
RUN mkdir -p /usr/local/share/ca-certificates/russian-trusted && \
  curl -fsSL https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt \
    -o /usr/local/share/ca-certificates/russian-trusted/russian_trusted_root_ca.crt && \
  curl -fsSL https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt \
    -o /usr/local/share/ca-certificates/russian-trusted/russian_trusted_sub_ca.crt && \
  chmod 644 /usr/local/share/ca-certificates/russian-trusted/*.crt && \
  update-ca-certificates --fresh

# Рабочая директория
WORKDIR /app

# Force pip to look at PyTorch CPU wheels for all installs
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu

# Pre-install CPU-only torch to prevent override by transitive deps and enable caching
# This layer will be cached unless the Dockerfile changes
RUN pip install --no-cache-dir --upgrade pip "setuptools<70" wheel setuptools wheel && \
  pip install --no-cache-dir torch==2.5.1+cpu torchaudio==2.5.1+cpu

# Копирование зависимостей
COPY requirements.txt .

# Установка остальных Python зависимостей
RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt

# Копирование кода приложения
COPY ./app /app/app

# Создание директории для логов и установка прав
RUN mkdir -p /app/logs && chown -R nonroot:nonroot /app/logs

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Healthcheck endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose порт
EXPOSE 8000

USER nonroot

# Запуск приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

