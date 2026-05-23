# Руководство по интеграции UI и API контракт

## Обзор

Данное руководство описывает API контракт Python AI Service и способы интеграции с различными пользовательскими интерфейсами (UI). Сервис предоставляет RESTful API для взаимодействия с LLM моделями, reasoning engines и базами данных.

## API Архитектура

### Структура API

```
FastAPI Application
    ↓
API Router (/api/v1/)
    ├── /chat - Чат эндпоинты
    ├── /assistants - Управление ассистентами
    ├── /threads - Управление потоками диалогов
    └── /models - Информация о моделях
```

### Основные компоненты

1. **API Layer** (`app/api/`) - HTTP эндпоинты
2. **Service Layer** (`app/services/`) - Бизнес-логика
3. **Models** (`app/models/`) - Pydantic модели для валидации

## API Эндпоинты

### 1. Chat API

#### POST /api/v1/chat/completions

Отправка сообщения и получение ответа.

**Request:**
```json
{
  "message": "Привет! Как дела?",
  "session_id": "optional-session-id",
  "model": "gigachat_pro",
  "reasoning_engine": "cot",
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false,
  "context": {
    "use_rag": true,
    "use_graph": false
  }
}
```

**Response (Non-streaming):**
```json
{
  "id": "msg_123456",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gigachat_pro",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Привет! У меня всё отлично, спасибо!"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  },
  "reasoning_metadata": {
    "engine": "cot",
    "steps": 4,
    "confidence": 0.95
  }
}
```

**Response (Streaming):**
```
data: {"id":"msg_123","object":"chat.completion.chunk","created":1234567890,"model":"gigachat_pro","choices":[{"index":0,"delta":{"role":"assistant","content":"Привет"},"finish_reason":null}]}

data: {"id":"msg_123","object":"chat.completion.chunk","created":1234567890,"model":"gigachat_pro","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

data: {"id":"msg_123","object":"chat.completion.chunk","created":1234567890,"model":"gigachat_pro","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Привет!",
    "model": "gigachat_pro",
    "stream": false
  }'
```

**Python Example:**
```python
import requests

response = requests.post(
    "http://localhost:8001/api/v1/chat/completions",
    json={
        "message": "Привет!",
        "model": "gigachat_pro",
        "stream": False
    }
)

data = response.json()
print(data["choices"][0]["message"]["content"])
```

**JavaScript Example:**
```javascript
fetch('http://localhost:8001/api/v1/chat/completions', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: 'Привет!',
    model: 'gigachat_pro',
    stream: false
  })
})
.then(response => response.json())
.then(data => {
  console.log(data.choices[0].message.content);
});
```

#### GET /api/v1/chat/sessions/{session_id}

Получить историю сессии.

**Response:**
```json
{
  "session_id": "sess_123",
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:05:00Z",
  "messages": [
    {
      "role": "user",
      "content": "Привет!",
      "timestamp": "2024-01-01T12:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Привет! Чем могу помочь?",
      "timestamp": "2024-01-01T12:00:05Z"
    }
  ],
  "metadata": {
    "model": "gigachat_pro",
    "total_tokens": 150
  }
}
```

### 2. Assistants API

#### POST /api/v1/assistants

Создать ассистента.

**Request:**
```json
{
  "name": "Мой ассистент",
  "description": "Помощник для анализа данных",
  "model": "gigachat_pro",
  "reasoning_engine": "reflection",
  "instructions": "Ты - эксперт по анализу данных...",
  "tools": ["rag", "graph_search"],
  "metadata": {
    "category": "analytics"
  }
}
```

**Response:**
```json
{
  "id": "asst_123",
  "object": "assistant",
  "created_at": 1234567890,
  "name": "Мой ассистент",
  "description": "Помощник для анализа данных",
  "model": "gigachat_pro",
  "reasoning_engine": "reflection",
  "instructions": "Ты - эксперт по анализу данных...",
  "tools": ["rag", "graph_search"],
  "metadata": {
    "category": "analytics"
  }
}
```

#### GET /api/v1/assistants

Список ассистентов.

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "asst_123",
      "name": "Мой ассистент",
      "model": "gigachat_pro"
    }
  ],
  "has_more": false
}
```

### 3. Threads API

#### POST /api/v1/threads

Создать поток диалога.

**Request:**
```json
{
  "assistant_id": "asst_123",
  "metadata": {
    "user_id": "user_456"
  }
}
```

**Response:**
```json
{
  "id": "thread_789",
  "object": "thread",
  "created_at": 1234567890,
  "assistant_id": "asst_123",
  "metadata": {
    "user_id": "user_456"
  }
}
```

#### POST /api/v1/threads/{thread_id}/messages

Добавить сообщение в поток.

**Request:**
```json
{
  "role": "user",
  "content": "Проанализируй эти данные"
}
```

#### POST /api/v1/threads/{thread_id}/runs

Запустить ассистента в потоке.

**Response:**
```json
{
  "id": "run_999",
  "object": "thread.run",
  "created_at": 1234567890,
  "thread_id": "thread_789",
  "assistant_id": "asst_123",
  "status": "in_progress"
}
```

### 4. Models API

#### GET /api/v1/models

Список доступных моделей.

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "gigachat",
      "object": "model",
      "created": 1234567890,
      "owned_by": "sber",
      "available": true
    },
    {
      "id": "gigachat_pro",
      "object": "model",
      "created": 1234567890,
      "owned_by": "sber",
      "available": true
    }
  ]
}
```

#### GET /api/v1/models/{model_id}

Информация о модели.

**Response:**
```json
{
  "id": "gigachat_pro",
  "object": "model",
  "created": 1234567890,
  "owned_by": "sber",
  "available": true,
  "config": {
    "temperature": 0.7,
    "max_tokens": 1500
  }
}
```

## Интеграция с UI

### React Example

```typescript
// api/chat.ts
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001/api/v1';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  model?: string;
  stream?: boolean;
}

export interface ChatResponse {
  id: string;
  choices: Array<{
    message: ChatMessage;
    finish_reason: string;
  }>;
  usage: {
    total_tokens: number;
  };
}

export const sendMessage = async (
  request: ChatRequest
): Promise<ChatResponse> => {
  const response = await axios.post(
    `${API_BASE_URL}/chat/completions`,
    request
  );
  return response.data;
};

export const streamMessage = async (
  request: ChatRequest,
  onChunk: (chunk: string) => void
): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ ...request, stream: true }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader!.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') return;

        try {
          const parsed = JSON.parse(data);
          const content = parsed.choices[0]?.delta?.content;
          if (content) {
            onChunk(content);
          }
        } catch (e) {
          console.error('Failed to parse chunk:', e);
        }
      }
    }
  }
};
```

```tsx
// components/ChatInterface.tsx
import React, { useState } from 'react';
import { sendMessage, streamMessage } from '../api/chat';

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Array<{role: string, content: string}>>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      // Non-streaming
      const response = await sendMessage({
        message: input,
        model: 'gigachat_pro',
        stream: false
      });

      const assistantMessage = {
        role: 'assistant',
        content: response.choices[0].message.content
      };
      setMessages(prev => [...prev, assistantMessage]);

      // OR Streaming
      // let assistantContent = '';
      // setMessages(prev => [...prev, { role: 'assistant', content: '' }]);
      //
      // await streamMessage(
      //   { message: input, model: 'gigachat_pro', stream: true },
      //   (chunk) => {
      //     assistantContent += chunk;
      //     setMessages(prev => {
      //       const newMessages = [...prev];
      //       newMessages[newMessages.length - 1].content = assistantContent;
      //       return newMessages;
      //     });
      //   }
      // );

    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-interface">
      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
      </div>

      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          disabled={loading}
          placeholder="Введите сообщение..."
        />
        <button onClick={handleSend} disabled={loading}>
          {loading ? 'Отправка...' : 'Отправить'}
        </button>
      </div>
    </div>
  );
};
```

### Vue.js Example

```typescript
// composables/useChat.ts
import { ref } from 'vue';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001/api/v1';

export const useChat = () => {
  const messages = ref<Array<{role: string, content: string}>>([]);
  const loading = ref(false);

  const sendMessage = async (message: string) => {
    messages.value.push({ role: 'user', content: message });
    loading.value = true;

    try {
      const response = await axios.post(
        `${API_BASE_URL}/chat/completions`,
        {
          message,
          model: 'gigachat_pro',
          stream: false
        }
      );

      messages.value.push({
        role: 'assistant',
        content: response.data.choices[0].message.content
      });
    } catch (error) {
      console.error('Error:', error);
    } finally {
      loading.value = false;
    }
  };

  return {
    messages,
    loading,
    sendMessage
  };
};
```

```vue
<!-- components/ChatInterface.vue -->
<template>
  <div class="chat-interface">
    <div class="messages">
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        :class="['message', msg.role]"
      >
        {{ msg.content }}
      </div>
    </div>

    <div class="input-area">
      <input
        v-model="input"
        @keypress.enter="handleSend"
        :disabled="loading"
        placeholder="Введите сообщение..."
      />
      <button @click="handleSend" :disabled="loading">
        {{ loading ? 'Отправка...' : 'Отправить' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useChat } from '../composables/useChat';

const { messages, loading, sendMessage } = useChat();
const input = ref('');

const handleSend = async () => {
  if (!input.value.trim()) return;
  await sendMessage(input.value);
  input.value = '';
};
</script>
```

### Mobile (React Native) Example

```typescript
// services/ChatService.ts
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001/api/v1';

export class ChatService {
  static async sendMessage(message: string, model: string = 'gigachat_pro') {
    try {
      const response = await axios.post(
        `${API_BASE_URL}/chat/completions`,
        {
          message,
          model,
          stream: false
        },
        {
          timeout: 30000 // 30 seconds
        }
      );

      return response.data.choices[0].message.content;
    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    }
  }
}
```

```tsx
// screens/ChatScreen.tsx
import React, { useState } from 'react';
import { View, TextInput, Button, FlatList, Text } from 'react-native';
import { ChatService } from '../services/ChatService';

export const ChatScreen: React.FC = () => {
  const [messages, setMessages] = useState<Array<{role: string, content: string}>>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;

    setMessages(prev => [...prev, { role: 'user', content: input }]);
    const userInput = input;
    setInput('');
    setLoading(true);

    try {
      const response = await ChatService.sendMessage(userInput);
      setMessages(prev => [...prev, { role: 'assistant', content: response }]);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1 }}>
      <FlatList
        data={messages}
        renderItem={({ item }) => (
          <View style={{ padding: 10 }}>
            <Text style={{ fontWeight: 'bold' }}>{item.role}:</Text>
            <Text>{item.content}</Text>
          </View>
        )}
        keyExtractor={(_, idx) => idx.toString()}
      />

      <View style={{ flexDirection: 'row', padding: 10 }}>
        <TextInput
          value={input}
          onChangeText={setInput}
          style={{ flex: 1, borderWidth: 1, padding: 10 }}
          placeholder="Введите сообщение..."
          editable={!loading}
        />
        <Button
          title={loading ? 'Отправка...' : 'Отправить'}
          onPress={handleSend}
          disabled={loading}
        />
      </View>
    </View>
  );
};
```

## WebSocket Support (Опционально)

Для real-time коммуникации можно добавить WebSocket поддержку:

```python
# app/api/websocket.py

from fastapi import WebSocket, WebSocketDisconnect
from app.services.chat_service import ChatService

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            # Получить сообщение от клиента
            data = await websocket.receive_json()
            
            message = data.get("message")
            model = data.get("model", "gigachat_pro")
            
            # Обработать сообщение
            chat_service = ChatService()
            
            async for chunk in chat_service.stream_response(message, model):
                # Отправить chunk клиенту
                await websocket.send_json({
                    "type": "chunk",
                    "content": chunk
                })
            
            # Отправить сигнал завершения
            await websocket.send_json({
                "type": "done"
            })
    
    except WebSocketDisconnect:
        print("Client disconnected")
```

**Client Example:**
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/chat');

ws.onopen = () => {
  ws.send(JSON.stringify({
    message: 'Привет!',
    model: 'gigachat_pro'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'chunk') {
    console.log('Chunk:', data.content);
  } else if (data.type === 'done') {
    console.log('Done!');
  }
};
```

## Аутентификация и авторизация

### JWT Authentication

```python
# app/api/auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка JWT токена."""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

# Использование в эндпоинтах
@app.post("/api/v1/chat/completions")
async def chat_completions(
    request: ChatRequest,
    user = Depends(verify_token)
):
    # user содержит данные из токена
    pass
```

**Client Example:**
```typescript
const token = 'your-jwt-token';

const response = await axios.post(
  'http://localhost:8001/api/v1/chat/completions',
  { message: 'Привет!' },
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);
```

## Error Handling

### Стандартные коды ошибок

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Missing required field: message",
    "type": "validation_error"
  }
}
```

**Коды ошибок:**
- `400` - Неверный запрос
- `401` - Не авторизован
- `403` - Доступ запрещен
- `404` - Не найдено
- `429` - Слишком много запросов
- `500` - Внутренняя ошибка сервера
- `503` - Сервис недоступен

### Client Error Handling

```typescript
try {
  const response = await sendMessage({ message: 'Привет!' });
} catch (error) {
  if (axios.isAxiosError(error)) {
    if (error.response) {
      // Ошибка от сервера
      const errorData = error.response.data.error;
      console.error(`Error ${errorData.code}: ${errorData.message}`);
      
      if (error.response.status === 429) {
        // Rate limit - повторить позже
        setTimeout(() => retry(), 5000);
      }
    } else if (error.request) {
      // Нет ответа от сервера
      console.error('No response from server');
    }
  }
}
```

## Rate Limiting

API использует rate limiting для защиты от злоупотреблений:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1234567890
```

## CORS Configuration

Для cross-origin запросов настройте CORS:

```python
# app/main.py

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## OpenAPI/Swagger Documentation

API документация доступна по адресу:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`
- OpenAPI JSON: `http://localhost:8001/openapi.json`

## Лучшие практики

### 1. Retry Logic

```typescript
const retry = async (fn: () => Promise<any>, maxRetries = 3) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
    }
  }
};
```

### 2. Request Cancellation

```typescript
const controller = new AbortController();

const response = await fetch('/api/v1/chat/completions', {
  method: 'POST',
  signal: controller.signal,
  body: JSON.stringify({ message: 'Привет!' })
});

// Отменить запрос
controller.abort();
```

### 3. Caching

```typescript
const cache = new Map();

const getCachedResponse = async (message: string) => {
  if (cache.has(message)) {
    return cache.get(message);
  }
  
  const response = await sendMessage({ message });
  cache.set(message, response);
  
  return response;
};
```

## Troubleshooting

### Проблема: CORS ошибки

**Решение**: Добавьте frontend URL в `allow_origins` в CORS middleware

### Проблема: Таймауты

**Решение**: Увеличьте timeout на клиенте или используйте streaming

### Проблема: Rate limiting

**Решение**: Добавьте exponential backoff и retry logic

## Ссылки

- [Architecture](../architecture.md)
- [API Code](../../app/api/)
- [OpenAPI Spec](../../docs/api/chat_api.yaml)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
