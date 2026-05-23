# Руководство по резервному копированию и восстановлению

## Обзор

Данное руководство описывает процедуры резервного копирования и восстановления данных Python AI Service, включая базы данных, конфигурации и состояние приложения.

## Стратегия резервного копирования

### Типы резервных копий

**Full Backup (Полное)**
- Полная копия всех данных
- Частота: Еженедельно
- Хранение: 4 недели

**Incremental Backup (Инкрементное)**
- Только изменения с последнего backup
- Частота: Ежедневно
- Хранение: 7 дней

**Continuous Backup (Непрерывное)**
- WAL (Write-Ahead Log) для PostgreSQL
- Binlog для MySQL
- Частота: Реал-тайм
- Хранение: 24 часа

### Компоненты для резервного копирования

1. **PostgreSQL** - Реляционные данные
2. **Neo4j** - Граф знаний
3. **Milvus/ChromaDB** - Векторные эмбеддинги
4. **Redis** - Кэш и сессии
5. **Конфигурации** - .env, config files
6. **Логи** - Application logs

## PostgreSQL

### Backup

#### Метод 1: pg_dump (Логический backup)

```bash
#!/bin/bash
# scripts/backup_postgres.sh

# Параметры
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="mydb"
DB_USER="postgres"
BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/postgres_${DB_NAME}_${DATE}.sql.gz"

# Создать директорию если не существует
mkdir -p $BACKUP_DIR

# Создать backup
PGPASSWORD=$DB_PASSWORD pg_dump \
  -h $DB_HOST \
  -p $DB_PORT \
  -U $DB_USER \
  -d $DB_NAME \
  --format=custom \
  --compress=9 \
  --file=$BACKUP_FILE

# Проверить успешность
if [ $? -eq 0 ]; then
  echo "Backup successful: $BACKUP_FILE"
  
  # Удалить старые backups (старше 7 дней)
  find $BACKUP_DIR -name "postgres_*.sql.gz" -mtime +7 -delete
else
  echo "Backup failed!"
  exit 1
fi
```

**Запустить:**
```bash
chmod +x scripts/backup_postgres.sh
./scripts/backup_postgres.sh
```

**Автоматизация (cron):**
```bash
# Добавить в crontab
crontab -e

# Ежедневно в 2:00 AM
0 2 * * * /path/to/scripts/backup_postgres.sh >> /var/log/postgres_backup.log 2>&1
```

#### Метод 2: pg_basebackup (Физический backup)

```bash
#!/bin/bash
# scripts/backup_postgres_base.sh

BACKUP_DIR="/backups/postgres/base"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/base_$DATE"

mkdir -p $BACKUP_PATH

pg_basebackup \
  -h localhost \
  -p 5432 \
  -U postgres \
  -D $BACKUP_PATH \
  -Ft \
  -z \
  -P \
  -X stream

echo "Base backup completed: $BACKUP_PATH"
```

#### Метод 3: Continuous Archiving (WAL)

**Настройка PostgreSQL:**
```bash
# /etc/postgresql/15/main/postgresql.conf

wal_level = replica
archive_mode = on
archive_command = 'test ! -f /backups/postgres/wal/%f && cp %p /backups/postgres/wal/%f'
max_wal_senders = 3
```

**Перезапустить:**
```bash
systemctl restart postgresql
```

### Restore

#### Из pg_dump

```bash
#!/bin/bash
# scripts/restore_postgres.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

# Остановить приложение
systemctl stop python-ai-service

# Удалить существующую БД
PGPASSWORD=$DB_PASSWORD psql \
  -h localhost \
  -U postgres \
  -c "DROP DATABASE IF EXISTS mydb;"

# Создать новую БД
PGPASSWORD=$DB_PASSWORD psql \
  -h localhost \
  -U postgres \
  -c "CREATE DATABASE mydb;"

# Восстановить из backup
PGPASSWORD=$DB_PASSWORD pg_restore \
  -h localhost \
  -U postgres \
  -d mydb \
  --verbose \
  $BACKUP_FILE

# Проверить
if [ $? -eq 0 ]; then
  echo "Restore successful"
  
  # Запустить приложение
  systemctl start python-ai-service
else
  echo "Restore failed!"
  exit 1
fi
```

**Запустить:**
```bash
./scripts/restore_postgres.sh /backups/postgres/postgres_mydb_20240101_020000.sql.gz
```

#### Point-in-Time Recovery (PITR)

```bash
#!/bin/bash
# scripts/restore_postgres_pitr.sh

TARGET_TIME="2024-01-01 12:00:00"
BASE_BACKUP="/backups/postgres/base/base_20240101_000000"
WAL_ARCHIVE="/backups/postgres/wal"

# Остановить PostgreSQL
systemctl stop postgresql

# Очистить data directory
rm -rf /var/lib/postgresql/15/main/*

# Восстановить base backup
tar -xzf $BASE_BACKUP/base.tar.gz -C /var/lib/postgresql/15/main/

# Создать recovery.conf
cat > /var/lib/postgresql/15/main/recovery.conf <<EOF
restore_command = 'cp $WAL_ARCHIVE/%f %p'
recovery_target_time = '$TARGET_TIME'
recovery_target_action = 'promote'
EOF

# Установить права
chown -R postgres:postgres /var/lib/postgresql/15/main/

# Запустить PostgreSQL
systemctl start postgresql

echo "PITR restore initiated to $TARGET_TIME"
```

## Neo4j

### Backup

```bash
#!/bin/bash
# scripts/backup_neo4j.sh

NEO4J_HOME="/var/lib/neo4j"
BACKUP_DIR="/backups/neo4j"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/neo4j_$DATE.backup"

mkdir -p $BACKUP_DIR

# Остановить Neo4j
systemctl stop neo4j

# Создать backup
tar -czf $BACKUP_FILE -C $NEO4J_HOME data

# Запустить Neo4j
systemctl start neo4j

# Проверить
if [ $? -eq 0 ]; then
  echo "Neo4j backup successful: $BACKUP_FILE"
  
  # Удалить старые backups
  find $BACKUP_DIR -name "neo4j_*.backup" -mtime +7 -delete
else
  echo "Neo4j backup failed!"
  exit 1
fi
```

**Или используя neo4j-admin:**
```bash
neo4j-admin database dump \
  --database=neo4j \
  --to=/backups/neo4j/neo4j_$(date +%Y%m%d_%H%M%S).dump
```

### Restore

```bash
#!/bin/bash
# scripts/restore_neo4j.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

# Остановить Neo4j
systemctl stop neo4j

# Очистить data directory
rm -rf /var/lib/neo4j/data/*

# Восстановить из backup
tar -xzf $BACKUP_FILE -C /var/lib/neo4j/

# Установить права
chown -R neo4j:neo4j /var/lib/neo4j/data

# Запустить Neo4j
systemctl start neo4j

echo "Neo4j restore completed"
```

**Или используя neo4j-admin:**
```bash
neo4j-admin database load \
  --from=/backups/neo4j/neo4j_20240101_020000.dump \
  --database=neo4j \
  --overwrite-destination=true
```

## Milvus

### Backup

```bash
#!/bin/bash
# scripts/backup_milvus.sh

MILVUS_DATA="/var/lib/milvus"
BACKUP_DIR="/backups/milvus"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/milvus_$DATE.tar.gz"

mkdir -p $BACKUP_DIR

# Остановить Milvus
docker-compose stop milvus-standalone

# Создать backup
tar -czf $BACKUP_FILE -C $MILVUS_DATA .

# Запустить Milvus
docker-compose start milvus-standalone

echo "Milvus backup completed: $BACKUP_FILE"

# Удалить старые backups
find $BACKUP_DIR -name "milvus_*.tar.gz" -mtime +7 -delete
```

### Restore

```bash
#!/bin/bash
# scripts/restore_milvus.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

# Остановить Milvus
docker-compose stop milvus-standalone

# Очистить data directory
rm -rf /var/lib/milvus/*

# Восстановить из backup
tar -xzf $BACKUP_FILE -C /var/lib/milvus/

# Запустить Milvus
docker-compose start milvus-standalone

echo "Milvus restore completed"
```

## ChromaDB

### Backup

```bash
#!/bin/bash
# scripts/backup_chroma.sh

CHROMA_DATA="./chroma_db"
BACKUP_DIR="/backups/chroma"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/chroma_$DATE.tar.gz"

mkdir -p $BACKUP_DIR

# Создать backup
tar -czf $BACKUP_FILE -C $CHROMA_DATA .

echo "ChromaDB backup completed: $BACKUP_FILE"

# Удалить старые backups
find $BACKUP_DIR -name "chroma_*.tar.gz" -mtime +7 -delete
```

### Restore

```bash
#!/bin/bash
# scripts/restore_chroma.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

# Остановить приложение
systemctl stop python-ai-service

# Очистить data directory
rm -rf ./chroma_db/*

# Восстановить из backup
tar -xzf $BACKUP_FILE -C ./chroma_db/

# Запустить приложение
systemctl start python-ai-service

echo "ChromaDB restore completed"
```

## Redis

### Backup

```bash
#!/bin/bash
# scripts/backup_redis.sh

REDIS_DATA="/var/lib/redis"
BACKUP_DIR="/backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/redis_$DATE.rdb"

mkdir -p $BACKUP_DIR

# Создать snapshot
redis-cli BGSAVE

# Дождаться завершения
while [ $(redis-cli LASTSAVE) -eq $(redis-cli LASTSAVE) ]; do
  sleep 1
done

# Копировать RDB файл
cp $REDIS_DATA/dump.rdb $BACKUP_FILE

echo "Redis backup completed: $BACKUP_FILE"

# Удалить старые backups
find $BACKUP_DIR -name "redis_*.rdb" -mtime +7 -delete
```

### Restore

```bash
#!/bin/bash
# scripts/restore_redis.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

# Остановить Redis
systemctl stop redis

# Восстановить RDB файл
cp $BACKUP_FILE /var/lib/redis/dump.rdb

# Установить права
chown redis:redis /var/lib/redis/dump.rdb

# Запустить Redis
systemctl start redis

echo "Redis restore completed"
```

## Конфигурации

### Backup

```bash
#!/bin/bash
# scripts/backup_configs.sh

CONFIG_DIRS=(
  "/etc/python-ai-service"
  "/etc/nginx/conf.d"
  "/etc/systemd/system"
)

APP_DIR="/opt/python-ai-service"
BACKUP_DIR="/backups/configs"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/configs_$DATE.tar.gz"

mkdir -p $BACKUP_DIR

# Создать временную директорию
TEMP_DIR=$(mktemp -d)

# Копировать конфигурации
for dir in "${CONFIG_DIRS[@]}"; do
  if [ -d "$dir" ]; then
    cp -r $dir $TEMP_DIR/
  fi
done

# Копировать .env
cp $APP_DIR/.env $TEMP_DIR/

# Создать архив
tar -czf $BACKUP_FILE -C $TEMP_DIR .

# Удалить временную директорию
rm -rf $TEMP_DIR

echo "Configs backup completed: $BACKUP_FILE"

# Удалить старые backups
find $BACKUP_DIR -name "configs_*.tar.gz" -mtime +30 -delete
```

### Restore

```bash
#!/bin/bash
# scripts/restore_configs.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file>"
  exit 1
fi

# Создать временную директорию
TEMP_DIR=$(mktemp -d)

# Распаковать архив
tar -xzf $BACKUP_FILE -C $TEMP_DIR

# Восстановить конфигурации
# (Осторожно! Может перезаписать текущие конфигурации)
cp -r $TEMP_DIR/etc/* /etc/
cp $TEMP_DIR/.env /opt/python-ai-service/

# Удалить временную директорию
rm -rf $TEMP_DIR

# Перезагрузить сервисы
systemctl daemon-reload
systemctl restart python-ai-service
systemctl restart nginx

echo "Configs restore completed"
```

## Полный backup всей системы

```bash
#!/bin/bash
# scripts/backup_full.sh

BACKUP_DIR="/backups/full"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$DATE"

mkdir -p $BACKUP_PATH

echo "Starting full backup..."

# PostgreSQL
echo "Backing up PostgreSQL..."
./scripts/backup_postgres.sh
cp /backups/postgres/postgres_*.sql.gz $BACKUP_PATH/

# Neo4j
echo "Backing up Neo4j..."
./scripts/backup_neo4j.sh
cp /backups/neo4j/neo4j_*.backup $BACKUP_PATH/

# Milvus
echo "Backing up Milvus..."
./scripts/backup_milvus.sh
cp /backups/milvus/milvus_*.tar.gz $BACKUP_PATH/

# Redis
echo "Backing up Redis..."
./scripts/backup_redis.sh
cp /backups/redis/redis_*.rdb $BACKUP_PATH/

# Configs
echo "Backing up configs..."
./scripts/backup_configs.sh
cp /backups/configs/configs_*.tar.gz $BACKUP_PATH/

# Создать манифест
cat > $BACKUP_PATH/manifest.txt <<EOF
Backup Date: $DATE
PostgreSQL: $(ls $BACKUP_PATH/postgres_*.sql.gz)
Neo4j: $(ls $BACKUP_PATH/neo4j_*.backup)
Milvus: $(ls $BACKUP_PATH/milvus_*.tar.gz)
Redis: $(ls $BACKUP_PATH/redis_*.rdb)
Configs: $(ls $BACKUP_PATH/configs_*.tar.gz)
EOF

echo "Full backup completed: $BACKUP_PATH"

# Удалить старые full backups (старше 4 недель)
find $BACKUP_DIR -maxdepth 1 -type d -mtime +28 -exec rm -rf {} \;
```

## Удаленное хранение

### AWS S3

```bash
#!/bin/bash
# scripts/upload_to_s3.sh

BACKUP_DIR="/backups"
S3_BUCKET="s3://my-backups/python-ai-service"

# Установить AWS CLI если не установлен
# apt-get install awscli

# Синхронизировать с S3
aws s3 sync $BACKUP_DIR $S3_BUCKET \
  --storage-class STANDARD_IA \
  --exclude "*" \
  --include "*.sql.gz" \
  --include "*.backup" \
  --include "*.tar.gz" \
  --include "*.rdb"

echo "Backups uploaded to S3"
```

**Автоматизация:**
```bash
# crontab
0 3 * * * /path/to/scripts/upload_to_s3.sh >> /var/log/s3_upload.log 2>&1
```

### Rsync на удаленный сервер

```bash
#!/bin/bash
# scripts/rsync_backups.sh

BACKUP_DIR="/backups"
REMOTE_HOST="backup-server.example.com"
REMOTE_USER="backup"
REMOTE_DIR="/backups/python-ai-service"

# Синхронизировать
rsync -avz --delete \
  -e "ssh -i /root/.ssh/backup_key" \
  $BACKUP_DIR/ \
  $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/

echo "Backups synced to remote server"
```

## Тестирование восстановления

### Процедура тестирования

```bash
#!/bin/bash
# scripts/test_restore.sh

echo "=== Backup & Restore Test ==="

# 1. Создать тестовые данные
echo "Creating test data..."
psql -U postgres -d mydb -c "INSERT INTO test_table VALUES (1, 'test');"

# 2. Создать backup
echo "Creating backup..."
./scripts/backup_postgres.sh

# 3. Удалить данные
echo "Deleting data..."
psql -U postgres -d mydb -c "DELETE FROM test_table WHERE id = 1;"

# 4. Восстановить из backup
echo "Restoring from backup..."
LATEST_BACKUP=$(ls -t /backups/postgres/postgres_*.sql.gz | head -1)
./scripts/restore_postgres.sh $LATEST_BACKUP

# 5. Проверить данные
echo "Verifying data..."
RESULT=$(psql -U postgres -d mydb -t -c "SELECT COUNT(*) FROM test_table WHERE id = 1;")

if [ "$RESULT" -eq 1 ]; then
  echo "✓ Restore test PASSED"
else
  echo "✗ Restore test FAILED"
  exit 1
fi
```

**Запускать ежемесячно:**
```bash
# crontab
0 4 1 * * /path/to/scripts/test_restore.sh >> /var/log/restore_test.log 2>&1
```

## Мониторинг backups

### Проверка успешности

```bash
#!/bin/bash
# scripts/check_backups.sh

BACKUP_DIR="/backups"
MAX_AGE_HOURS=24

# Проверить PostgreSQL backup
LATEST_PG=$(find $BACKUP_DIR/postgres -name "postgres_*.sql.gz" -mtime -1 | wc -l)
if [ $LATEST_PG -eq 0 ]; then
  echo "WARNING: No recent PostgreSQL backup found!"
fi

# Проверить Neo4j backup
LATEST_NEO4J=$(find $BACKUP_DIR/neo4j -name "neo4j_*.backup" -mtime -1 | wc -l)
if [ $LATEST_NEO4J -eq 0 ]; then
  echo "WARNING: No recent Neo4j backup found!"
fi

# Проверить размеры backups
PG_SIZE=$(du -sh $BACKUP_DIR/postgres | cut -f1)
echo "PostgreSQL backups size: $PG_SIZE"

NEO4J_SIZE=$(du -sh $BACKUP_DIR/neo4j | cut -f1)
echo "Neo4j backups size: $NEO4J_SIZE"
```

### Алерты

```python
# scripts/backup_monitor.py

import os
import time
import requests
from datetime import datetime, timedelta

BACKUP_DIR = "/backups"
SLACK_WEBHOOK = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

def check_backup_age(backup_type, max_age_hours=24):
    """Проверить возраст последнего backup."""
    backup_path = os.path.join(BACKUP_DIR, backup_type)
    
    if not os.path.exists(backup_path):
        return False, "Backup directory not found"
    
    files = [f for f in os.listdir(backup_path) if f.endswith(('.sql.gz', '.backup', '.tar.gz'))]
    
    if not files:
        return False, "No backup files found"
    
    latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(backup_path, f)))
    latest_time = datetime.fromtimestamp(os.path.getmtime(os.path.join(backup_path, latest_file)))
    
    age = datetime.now() - latest_time
    
    if age > timedelta(hours=max_age_hours):
        return False, f"Latest backup is {age.total_seconds() / 3600:.1f} hours old"
    
    return True, f"Latest backup: {latest_file}"

def send_alert(message):
    """Отправить алерт в Slack."""
    requests.post(SLACK_WEBHOOK, json={"text": message})

# Проверить все backups
for backup_type in ["postgres", "neo4j", "milvus", "redis"]:
    success, message = check_backup_age(backup_type)
    
    if not success:
        alert = f"⚠️ Backup Alert: {backup_type} - {message}"
        print(alert)
        send_alert(alert)
```

## Disaster Recovery Plan

### RTO и RPO

**RTO (Recovery Time Objective):**
- Critical: 1 час
- High: 4 часа
- Medium: 24 часа

**RPO (Recovery Point Objective):**
- Critical: 15 минут (continuous backup)
- High: 1 час (incremental backup)
- Medium: 24 часа (daily backup)

### Процедура DR

1. **Оценка ситуации** (5 минут)
   - Определить масштаб проблемы
   - Оценить потерю данных
   - Определить приоритеты

2. **Подготовка инфраструктуры** (15 минут)
   - Поднять новые серверы (если нужно)
   - Настроить сеть
   - Установить зависимости

3. **Восстановление данных** (30 минут)
   - PostgreSQL
   - Neo4j
   - Milvus
   - Redis

4. **Восстановление приложения** (10 минут)
   - Развернуть код
   - Восстановить конфигурации
   - Запустить сервисы

5. **Проверка** (10 минут)
   - Health checks
   - Функциональное тестирование
   - Мониторинг

## Чеклист

### Ежедневно
- [ ] Проверить успешность автоматических backups
- [ ] Проверить размер backups
- [ ] Проверить свободное место на диске

### Еженедельно
- [ ] Проверить integrity backups
- [ ] Синхронизировать с удаленным хранилищем
- [ ] Обновить документацию

### Ежемесячно
- [ ] Провести тест восстановления
- [ ] Проверить DR процедуры
- [ ] Очистить старые backups

## Ссылки

- [Architecture](../architecture.md)
- [Incident Response](./incident_response.md)
- [Scaling Guide](./scaling.md)
