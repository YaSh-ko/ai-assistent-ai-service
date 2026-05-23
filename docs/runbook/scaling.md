# Руководство по масштабированию

## Обзор

Данное руководство описывает стратегии и процедуры масштабирования Python AI Service для обработки увеличенной нагрузки и обеспечения высокой доступности.

## Типы масштабирования

### Вертикальное масштабирование (Scale Up)

Увеличение ресурсов существующих серверов.

**Преимущества:**
- Простота реализации
- Не требует изменений в архитектуре
- Меньше сложности в управлении

**Недостатки:**
- Ограничено аппаратными возможностями
- Единая точка отказа
- Дороже при больших масштабах

### Горизонтальное масштабирование (Scale Out)

Добавление дополнительных серверов.

**Преимущества:**
- Практически неограниченная масштабируемость
- Высокая доступность
- Отказоустойчивость

**Недостатки:**
- Сложнее в реализации
- Требует балансировки нагрузки
- Управление состоянием

## Компоненты для масштабирования

### 1. API Layer (FastAPI)

#### Вертикальное масштабирование

**Увеличение workers:**
```bash
# В .env
WORKERS=8  # вместо 4

# Или через uvicorn
uvicorn app.main:app --workers 8 --host 0.0.0.0 --port 8001
```

**Увеличение ресурсов:**
```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
```

#### Горизонтальное масштабирование

**Docker Compose:**
```bash
# Запустить 3 инстанса
docker-compose up -d --scale api=3
```

**Kubernetes:**
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: python-ai-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: python-ai-service
  template:
    metadata:
      labels:
        app: python-ai-service
    spec:
      containers:
      - name: api
        image: python-ai-service:latest
        ports:
        - containerPort: 8001
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        env:
        - name: WORKERS
          value: "4"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: python-ai-service
spec:
  selector:
    app: python-ai-service
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8001
  type: LoadBalancer
```

**Применить:**
```bash
kubectl apply -f deployment.yaml

# Масштабировать
kubectl scale deployment python-ai-service --replicas=5

# Автомасштабирование
kubectl autoscale deployment python-ai-service --min=3 --max=10 --cpu-percent=70
```

### 2. Load Balancer

#### Nginx

```nginx
# /etc/nginx/conf.d/python-ai-service.conf

upstream api_backend {
    least_conn;  # Алгоритм балансировки
    
    server 10.0.1.10:8001 weight=1 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8001 weight=1 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:8001 weight=1 max_fails=3 fail_timeout=30s;
    
    keepalive 32;
}

server {
    listen 80;
    server_name api.example.com;
    
    location / {
        proxy_pass http://api_backend;
        proxy_http_version 1.1;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Для WebSocket
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://api_backend/health;
    }
}
```

**Применить:**
```bash
nginx -t
systemctl reload nginx
```

#### HAProxy

```haproxy
# /etc/haproxy/haproxy.cfg

global
    maxconn 4096
    log /dev/log local0
    log /dev/log local1 notice

defaults
    log global
    mode http
    option httplog
    option dontlognull
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend api_frontend
    bind *:80
    default_backend api_backend
    
    # Rate limiting
    stick-table type ip size 100k expire 30s store http_req_rate(10s)
    http-request track-sc0 src
    http-request deny if { sc_http_req_rate(0) gt 100 }

backend api_backend
    balance leastconn
    option httpchk GET /health
    
    server api1 10.0.1.10:8001 check inter 2s fall 3 rise 2
    server api2 10.0.1.11:8001 check inter 2s fall 3 rise 2
    server api3 10.0.1.12:8001 check inter 2s fall 3 rise 2
```

**Применить:**
```bash
haproxy -c -f /etc/haproxy/haproxy.cfg
systemctl reload haproxy
```

### 3. База данных

#### PostgreSQL

**Read Replicas:**
```yaml
# docker-compose.yml
services:
  postgres-primary:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: password
    volumes:
      - postgres-primary-data:/var/lib/postgresql/data
    command: >
      postgres
      -c wal_level=replica
      -c max_wal_senders=3
      -c max_replication_slots=3
  
  postgres-replica1:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: password
    volumes:
      - postgres-replica1-data:/var/lib/postgresql/data
    command: >
      postgres
      -c hot_standby=on
```

**Connection Pooling (PgBouncer):**
```ini
# /etc/pgbouncer/pgbouncer.ini

[databases]
mydb = host=localhost port=5432 dbname=mydb

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 3
```

**Применить:**
```bash
systemctl restart pgbouncer

# В приложении использовать:
# DATABASE_URL=postgresql://user:pass@localhost:6432/mydb
```

#### Neo4j

**Кластер:**
```yaml
# docker-compose.yml
services:
  neo4j-core1:
    image: neo4j:5-enterprise
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_dbms_mode: CORE
      NEO4J_causal__clustering_initial__discovery__members: neo4j-core1:5000,neo4j-core2:5000,neo4j-core3:5000
    ports:
      - "7474:7474"
      - "7687:7687"
  
  neo4j-core2:
    image: neo4j:5-enterprise
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_dbms_mode: CORE
      NEO4J_causal__clustering_initial__discovery__members: neo4j-core1:5000,neo4j-core2:5000,neo4j-core3:5000
  
  neo4j-core3:
    image: neo4j:5-enterprise
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_dbms_mode: CORE
      NEO4J_causal__clustering_initial__discovery__members: neo4j-core1:5000,neo4j-core2:5000,neo4j-core3:5000
```

#### Milvus

**Кластер:**
```yaml
# docker-compose.yml
version: '3.5'

services:
  etcd:
    image: quay.io/coreos/etcd:v3.5.0
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
    volumes:
      - etcd-data:/etcd

  minio:
    image: minio/minio:RELEASE.2023-03-20T20-16-18Z
    environment:
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    volumes:
      - minio-data:/minio_data
    command: minio server /minio_data

  milvus-standalone:
    image: milvusdb/milvus:v2.3.0
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    volumes:
      - milvus-data:/var/lib/milvus
    ports:
      - "19530:19530"
      - "9091:9091"
    depends_on:
      - etcd
      - minio

volumes:
  etcd-data:
  minio-data:
  milvus-data:
```

### 4. Кэширование

#### Redis Cluster

```yaml
# docker-compose.yml
services:
  redis-node1:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes
    ports:
      - "7001:6379"
  
  redis-node2:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes
    ports:
      - "7002:6379"
  
  redis-node3:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000 --appendonly yes
    ports:
      - "7003:6379"
```

**Создать кластер:**
```bash
redis-cli --cluster create \
  127.0.0.1:7001 \
  127.0.0.1:7002 \
  127.0.0.1:7003 \
  --cluster-replicas 0
```

## Автомасштабирование

### Kubernetes HPA (Horizontal Pod Autoscaler)

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: python-ai-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: python-ai-service
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
      - type: Pods
        value: 2
        periodSeconds: 30
      selectPolicy: Max
```

**Применить:**
```bash
kubectl apply -f hpa.yaml

# Проверить статус
kubectl get hpa
kubectl describe hpa python-ai-service-hpa
```

### AWS Auto Scaling

```python
# terraform/autoscaling.tf

resource "aws_autoscaling_group" "api" {
  name                = "python-ai-service-asg"
  vpc_zone_identifier = var.subnet_ids
  target_group_arns   = [aws_lb_target_group.api.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300
  
  min_size         = 3
  max_size         = 10
  desired_capacity = 3
  
  launch_template {
    id      = aws_launch_template.api.id
    version = "$Latest"
  }
  
  tag {
    key                 = "Name"
    value               = "python-ai-service"
    propagate_at_launch = true
  }
}

resource "aws_autoscaling_policy" "scale_up" {
  name                   = "scale-up"
  scaling_adjustment     = 2
  adjustment_type        = "ChangeInCapacity"
  cooldown               = 300
  autoscaling_group_name = aws_autoscaling_group.api.name
}

resource "aws_autoscaling_policy" "scale_down" {
  name                   = "scale-down"
  scaling_adjustment     = -1
  adjustment_type        = "ChangeInCapacity"
  cooldown               = 300
  autoscaling_group_name = aws_autoscaling_group.api.name
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "cpu-utilization-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "120"
  statistic           = "Average"
  threshold           = "70"
  
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.api.name
  }
  
  alarm_actions = [aws_autoscaling_policy.scale_up.arn]
}

resource "aws_cloudwatch_metric_alarm" "cpu_low" {
  alarm_name          = "cpu-utilization-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "120"
  statistic           = "Average"
  threshold           = "30"
  
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.api.name
  }
  
  alarm_actions = [aws_autoscaling_policy.scale_down.arn]
}
```

## Мониторинг масштабирования

### Метрики для отслеживания

**API Layer:**
- Requests per second (RPS)
- Response time (p50, p95, p99)
- Error rate
- CPU utilization
- Memory utilization
- Active connections

**Database:**
- Query latency
- Connection pool usage
- Replication lag
- Disk I/O
- Cache hit rate

**LLM API:**
- Request latency
- Rate limit usage
- Error rate
- Token usage

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Python AI Service - Scaling Metrics",
    "panels": [
      {
        "title": "Requests per Second",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "Active Pods",
        "targets": [
          {
            "expr": "count(kube_pod_info{namespace=\"default\", pod=~\"python-ai-service.*\"})"
          }
        ]
      },
      {
        "title": "CPU Usage",
        "targets": [
          {
            "expr": "avg(rate(container_cpu_usage_seconds_total{pod=~\"python-ai-service.*\"}[5m])) * 100"
          }
        ]
      }
    ]
  }
}
```

## Стратегии масштабирования

### 1. Reactive Scaling (Реактивное)

Масштабирование в ответ на текущую нагрузку.

**Когда использовать:**
- Непредсказуемая нагрузка
- Ограниченный бюджет
- Быстрые изменения трафика

**Пример:**
```yaml
# HPA с метриками CPU/Memory
minReplicas: 2
maxReplicas: 10
targetCPUUtilizationPercentage: 70
```

### 2. Predictive Scaling (Предиктивное)

Масштабирование на основе прогнозов.

**Когда использовать:**
- Предсказуемые паттерны нагрузки
- Критичная latency
- Достаточно исторических данных

**Пример:**
```python
# scripts/predictive_scaling.py

import pandas as pd
from sklearn.linear_model import LinearRegression

def predict_load(historical_data):
    """Прогноз нагрузки на следующий час."""
    model = LinearRegression()
    X = historical_data[['hour', 'day_of_week']]
    y = historical_data['requests_per_second']
    
    model.fit(X, y)
    
    # Прогноз
    next_hour = pd.DataFrame({
        'hour': [datetime.now().hour + 1],
        'day_of_week': [datetime.now().weekday()]
    })
    
    predicted_rps = model.predict(next_hour)[0]
    
    # Рассчитать необходимое количество pods
    rps_per_pod = 100
    required_pods = int(predicted_rps / rps_per_pod) + 1
    
    return required_pods
```

### 3. Scheduled Scaling (По расписанию)

Масштабирование по заранее определенному расписанию.

**Когда использовать:**
- Известные пики нагрузки
- Регулярные паттерны (рабочие часы)
- Плановые события

**Пример (Kubernetes CronJob):**
```yaml
# scale-up-morning.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-up-morning
spec:
  schedule: "0 8 * * 1-5"  # 8:00 по будням
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: kubectl
            image: bitnami/kubectl:latest
            command:
            - /bin/sh
            - -c
            - kubectl scale deployment python-ai-service --replicas=10
          restartPolicy: OnFailure

---
# scale-down-evening.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: scale-down-evening
spec:
  schedule: "0 20 * * 1-5"  # 20:00 по будням
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: kubectl
            image: bitnami/kubectl:latest
            command:
            - /bin/sh
            - -c
            - kubectl scale deployment python-ai-service --replicas=3
          restartPolicy: OnFailure
```

## Оптимизация производительности

### 1. Кэширование

```python
# app/cache/response_cache.py

from functools import lru_cache
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_response(ttl=3600):
    """Декоратор для кэширования ответов."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Генерация ключа кэша
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # Проверка кэша
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Выполнение функции
            result = await func(*args, **kwargs)
            
            # Сохранение в кэш
            redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result)
            )
            
            return result
        return wrapper
    return decorator
```

### 2. Connection Pooling

```python
# app/core/database.py

import asyncpg

class DatabasePool:
    _pool = None
    
    @classmethod
    async def get_pool(cls):
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host='localhost',
                port=5432,
                user='postgres',
                password='password',
                database='mydb',
                min_size=10,
                max_size=20,
                command_timeout=60
            )
        return cls._pool
```

### 3. Async Processing

```python
# app/services/async_service.py

import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

async def process_batch(items):
    """Параллельная обработка batch."""
    tasks = [process_item(item) for item in items]
    results = await asyncio.gather(*tasks)
    return results

async def process_item(item):
    """Обработка одного элемента."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor,
        heavy_computation,
        item
    )
    return result
```

## Чеклист масштабирования

### Перед масштабированием
- [ ] Проанализировать текущую нагрузку
- [ ] Определить bottlenecks
- [ ] Оценить стоимость
- [ ] Подготовить план rollback
- [ ] Настроить мониторинг

### Во время масштабирования
- [ ] Постепенное увеличение нагрузки
- [ ] Мониторинг метрик
- [ ] Проверка health checks
- [ ] Тестирование функциональности

### После масштабирования
- [ ] Проверить все компоненты
- [ ] Провести нагрузочное тестирование
- [ ] Обновить документацию
- [ ] Настроить алерты

## Ссылки

- [Architecture](../architecture.md)
- [Incident Response](./incident_response.md)
- [Monitoring Guide](./monitoring.md)
- [Backup & Restore](./backup_restore.md)
