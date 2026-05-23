# GigaChat SSL Verification Enabled

## Date: 2026-02-24

## Background
Previously, SSL verification was disabled for GigaChat API connections because the service uses certificates signed by Russian Certificate Authorities that weren't in the system trust store. This created a security vulnerability (MITM attacks).

## Solution
The Dockerfile now includes Russian trusted root certificates:
```dockerfile
# Российские корневые сертификаты для GigaChat / Sberbank API
RUN mkdir -p /usr/local/share/ca-certificates/russian-trusted && \
  curl -fsSL https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt \
    -o /usr/local/share/ca-certificates/russian-trusted/russian_trusted_root_ca.crt && \
  curl -fsSL https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt \
    -o /usr/local/share/ca-certificates/russian-trusted/russian_trusted_sub_ca.crt && \
  chmod 644 /usr/local/share/ca-certificates/russian-trusted/*.crt && \
  update-ca-certificates --fresh
```

With these certificates installed, we can now enable SSL verification.

## Changes Made

### 1. GigaChatProvider (app/providers/models/gigachat_provider.py)

**Before:**
```python
async def _get_session(self) -> aiohttp.ClientSession:
    if self._session is None or self._session.closed:
        # SSL context без проверки сертификата
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self._session = aiohttp.ClientSession(connector=connector)
    return self._session
```

**After:**
```python
async def _get_session(self) -> aiohttp.ClientSession:
    if self._session is None or self._session.closed:
        # SSL context с проверкой сертификата
        # Российские корневые сертификаты установлены в Docker образе
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self._session = aiohttp.ClientSession(connector=connector)
    return self._session
```

### 2. GigaChatEmbeddings (app/providers/embeddings/gigachat_embeddings.py)

**Before:**
```python
# Disable SSL verification warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger.warning("GigaChat SSL verification is disabled - connection is vulnerable to MITM attacks")

# In methods:
async with httpx.AsyncClient(verify=False) as client:
    ...
```

**After:**
```python
# In __init__:
logger.info("GigaChat SSL verification is enabled - using Russian trusted root certificates")

# In methods:
async with httpx.AsyncClient(verify=True) as client:
    ...
```

## Security Improvements

### Before (Insecure)
- ❌ SSL verification disabled (`verify=False`, `check_hostname=False`)
- ❌ Vulnerable to Man-in-the-Middle (MITM) attacks
- ❌ No certificate validation
- ❌ Warning messages in logs about security risks

### After (Secure)
- ✅ SSL verification enabled (`verify=True`, `check_hostname=True`)
- ✅ Protected against MITM attacks
- ✅ Full certificate chain validation
- ✅ Uses system trust store with Russian CA certificates
- ✅ Complies with security best practices

## Testing

### In Docker (Recommended)
The certificates are installed in the Docker image, so SSL verification will work:

```bash
# Build the Docker image
docker build -t python-ai-service .

# Run the service
docker-compose up
```

### Local Development (Without Docker)
If running locally without Docker, you'll need to install the Russian CA certificates manually:

```bash
# Download certificates
sudo mkdir -p /usr/local/share/ca-certificates/russian-trusted
sudo curl -fsSL https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt \
  -o /usr/local/share/ca-certificates/russian-trusted/russian_trusted_root_ca.crt
sudo curl -fsSL https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt \
  -o /usr/local/share/ca-certificates/russian-trusted/russian_trusted_sub_ca.crt
sudo chmod 644 /usr/local/share/ca-certificates/russian-trusted/*.crt
sudo update-ca-certificates --fresh
```

### Verification
After starting the service, check the logs:
- ✅ Should see: `"GigaChat SSL verification is enabled - using Russian trusted root certificates"`
- ✅ No SSL certificate errors
- ✅ Successful authentication and API calls

If you see SSL certificate errors, it means the certificates aren't properly installed.

## Rollback (If Needed)

If SSL verification causes issues, you can temporarily disable it by reverting the changes:

**GigaChatProvider:**
```python
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE  # Add this line
```

**GigaChatEmbeddings:**
```python
async with httpx.AsyncClient(verify=False) as client:
```

However, this should only be done as a last resort for debugging. The proper solution is to ensure the certificates are correctly installed.

## Certificate Details

**Russian Trusted Root CA:**
- URL: https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt
- Purpose: Root certificate for Russian Certificate Authority
- Used by: Sberbank, GigaChat, and other Russian services

**Russian Trusted Sub CA:**
- URL: https://gu-st.ru/content/lending/russian_trusted_sub_ca_pem.crt
- Purpose: Intermediate certificate
- Used by: Services signed by Russian CA

## Notes

- The certificates are automatically updated in the Docker image during build
- The `update-ca-certificates --fresh` command rebuilds the system trust store
- Both `aiohttp` (GigaChatProvider) and `httpx` (GigaChatEmbeddings) use the system trust store
- SSL verification is now consistent across all GigaChat API calls (auth, chat, embeddings)
