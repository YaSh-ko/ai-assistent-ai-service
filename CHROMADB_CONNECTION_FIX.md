# ChromaDB Connection Fix

## Problem
The service was trying to connect to ChromaDB but encountering errors:
- 405 Method Not Allowed when ChromaDB tried to authenticate
- 500 Internal Server Error on chat endpoints
- Thread creation failures

## Root Cause
ChromaDB is behind a reverse proxy at `https://api.delez-repo.ru/chroma/` but the Python client doesn't natively support URL paths in the traditional host/port configuration.

## Solution
Updated the ChromaProvider to handle full URLs with paths:
1. Pass the full URL `https://api.delez-repo.ru/chroma` as the host parameter
2. The chromadb.HttpClient can accept full URLs and will parse them correctly
3. Updated `.env` to use the full URL

### Configuration in `.env`
```bash
CHROMA_SERVER_HOST=https://api.delez-repo.ru/chroma
CHROMA_SERVER_PORT=443
CHROMA_SERVER_SSL=True
```

### How it works
- When the provider detects a full URL with a path (e.g., `/chroma`), it passes the entire URL to `chromadb.HttpClient(host=full_url)`
- The client handles the URL parsing internally
- For standard host/port configs (no path), it uses the traditional `HttpClient(host, port, ssl)` approach

## SSL Security Context

### Why SSL is enabled for external ChromaDB (SECURE)
- Connecting to `api.delez-repo.ru` over HTTPS
- SSL certificate is valid for the domain
- Traffic is encrypted end-to-end
- This is the secure production configuration

### Why SSL verification is disabled for GigaChat (NECESSARY RISK)
- GigaChat API uses self-signed certificates
- `verify=False` is required to connect
- This creates a Man-in-the-Middle (MITM) vulnerability
- But it's documented in GigaChat's official documentation
- Alternative: Add GigaChat's certificate to system trust store

### Production SSL (SECURE)
- External clients connect via HTTPS to `api.delez-repo.ru`
- SSL termination happens at reverse proxy (nginx/caddy)
- Internal services can communicate without SSL (behind the proxy)
- This is standard production architecture

## Deployment Configurations

### External ChromaDB (current - through reverse proxy)
```bash
# Service connects to ChromaDB through reverse proxy
CHROMA_SERVER_HOST=https://api.delez-repo.ru/chroma
CHROMA_SERVER_PORT=443
CHROMA_SERVER_SSL=True
```

### Local Docker ChromaDB (for local development)
```bash
# Service runs locally, ChromaDB in Docker
CHROMA_SERVER_HOST=localhost
CHROMA_SERVER_PORT=8001
CHROMA_SERVER_SSL=False
```

### Production Docker (container-to-container)
```bash
# Both services run in Docker with docker-compose
# Use internal Docker network name
CHROMA_SERVER_HOST=staging_chroma
CHROMA_SERVER_PORT=8000
CHROMA_SERVER_SSL=False
```

## Testing the Connection
You can verify ChromaDB is accessible at:
```bash
curl https://api.delez-repo.ru/chroma/api/v2/heartbeat
```

Should return: `{"nanosecond heartbeat": <timestamp>}`

## Next Steps
1. Restart the service: `./start_service.sh`
2. Verify ChromaDB connection in logs - should see "Using full ChromaDB URL: https://api.delez-repo.ru/chroma"
3. Test chat functionality
4. The 404 thread errors will resolve once you create a new thread (old thread IDs are lost on restart since they're in-memory)
