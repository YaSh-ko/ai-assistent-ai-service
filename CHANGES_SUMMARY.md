# Changes Summary - Recent Updates

## Date: 2026-02-24

## Change 1: ChromaDB External Connection Fix

### Problem
Service couldn't connect to ChromaDB through the reverse proxy at `https://api.delez-repo.ru/chroma/` because:
1. The chromadb Python client doesn't natively support URL paths in host/port configuration
2. Previous attempts to connect were failing with 405 Method Not Allowed errors

### Changes Made

#### 1. Updated `.env` Configuration
**File:** `.env`

Changed ChromaDB connection to use full URL:
```bash
CHROMA_SERVER_HOST=https://api.delez-repo.ru/chroma
CHROMA_SERVER_PORT=443
CHROMA_SERVER_SSL=True
```

#### 2. Updated ChromaProvider to Handle Full URLs
**File:** `app/providers/databases/chroma_provider.py`

Modified the `__init__` method to:
- Detect when `CHROMA_SERVER_HOST` contains a full URL with path
- Pass the full URL directly to `chromadb.HttpClient(host=full_url)`
- Fall back to traditional `host/port/ssl` parameters for simple hostnames
- Added logging to show which connection method is being used

**Key Logic:**
```python
if host.startswith("http://") or host.startswith("https://"):
    logger.info(f"Using full ChromaDB URL: {host}")
    self._http_client = chromadb.HttpClient(host=host)
else:
    # Standard connection without path
    self._http_client = chromadb.HttpClient(host=host, port=port, ssl=ssl)
```

#### 3. Updated Documentation
**File:** `CHROMADB_CONNECTION_FIX.md`

Added comprehensive documentation covering:
- Problem description and root cause
- Solution explanation
- SSL security context
- Different deployment configurations
- Testing instructions

---

## Change 2: GigaChat SSL Verification Enabled

### Problem
SSL verification was disabled for GigaChat API connections (`verify=False`, `check_hostname=False`), creating a security vulnerability (MITM attacks). This was necessary because GigaChat uses certificates signed by Russian Certificate Authorities that weren't in the system trust store.

### Solution
The Dockerfile already includes Russian trusted root certificates, so we can now enable SSL verification.

### Changes Made

#### 1. GigaChatProvider SSL Verification
**File:** `app/providers/models/gigachat_provider.py`

**Before:**
```python
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
```

**After:**
```python
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED
```

#### 2. GigaChatEmbeddings SSL Verification
**File:** `app/providers/embeddings/gigachat_embeddings.py`

**Before:**
```python
# Disable SSL verification
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
async with httpx.AsyncClient(verify=False) as client:
```

**After:**
```python
# SSL verification enabled
logger.info("GigaChat SSL verification is enabled - using Russian trusted root certificates")
async with httpx.AsyncClient(verify=True) as client:
```

#### 3. Security Improvements
- ✅ SSL verification enabled for all GigaChat API calls
- ✅ Protected against MITM attacks
- ✅ Full certificate chain validation
- ✅ Uses system trust store with Russian CA certificates
- ✅ Complies with security best practices

#### 4. Documentation
**File:** `GIGACHAT_SSL_VERIFICATION_ENABLED.md`

Added comprehensive documentation covering:
- Background and problem description
- Solution with code examples
- Security improvements comparison
- Testing instructions for Docker and local development
- Rollback instructions if needed
- Certificate details

---

## How to Test All Changes

### 1. ChromaDB Connection
```bash
# Verify ChromaDB is accessible
curl https://api.delez-repo.ru/chroma/api/v2/heartbeat

# Restart the service
./start_service.sh

# Check logs for successful connection
# Look for: "Using full ChromaDB URL: https://api.delez-repo.ru/chroma"
```

### 2. GigaChat SSL Verification
```bash
# For Docker deployment (recommended)
docker build -t python-ai-service .
docker-compose up

# Check logs for:
# "GigaChat SSL verification is enabled - using Russian trusted root certificates"
# No SSL certificate errors
# Successful authentication and API calls
```

### 3. Full Integration Test
```bash
# Test chat functionality
# - Create a new thread
# - Send a message
# - Verify response is generated
# - Check that both ChromaDB and GigaChat work correctly
```

---

## Configuration Options

### ChromaDB Connection Modes

#### Mode 1: External with Path (Current)
```bash
CHROMA_SERVER_HOST=https://api.delez-repo.ru/chroma
CHROMA_SERVER_PORT=443
CHROMA_SERVER_SSL=True
```

#### Mode 2: Local Docker
```bash
CHROMA_SERVER_HOST=localhost
CHROMA_SERVER_PORT=8001
CHROMA_SERVER_SSL=False
```

#### Mode 3: Docker Network
```bash
CHROMA_SERVER_HOST=staging_chroma
CHROMA_SERVER_PORT=8000
CHROMA_SERVER_SSL=False
```

---

## Notes

### ChromaDB
- The chromadb.HttpClient can accept full URLs in the `host` parameter
- When a path is detected, the entire URL is passed as-is
- SSL is properly enabled for external connections
- The provider automatically handles URL parsing and validation

### GigaChat SSL
- The certificates are automatically updated in the Docker image during build
- The `update-ca-certificates --fresh` command rebuilds the system trust store
- Both `aiohttp` (GigaChatProvider) and `httpx` (GigaChatEmbeddings) use the system trust store
- SSL verification is now consistent across all GigaChat API calls (auth, chat, embeddings)
- For local development without Docker, certificates must be installed manually
