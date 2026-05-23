# GigaChat Authentication Troubleshooting

## Common Error: "Can't decode 'Authorization' header"

### Symptoms
```
ERROR | GigaChat auth failed: 400 - {"code":4,"message":"Can't decode 'Authorization' header"}
```

### Root Cause

The GigaChat provider supports two authentication methods:

1. **GIGACHAT_CREDENTIALS** - Pre-encoded base64 string
2. **GIGACHAT_CLIENT_ID + GIGACHAT_CLIENT_SECRET** - Separate credentials

When both are present in `.env`, the code prioritizes `GIGACHAT_CREDENTIALS`, which may cause encoding issues.

### Solution

**Option 1: Use CLIENT_ID and CLIENT_SECRET (Recommended)**

In your `.env` file, comment out `GIGACHAT_CREDENTIALS`:

```bash
# GIGACHAT_CREDENTIALS=MDE5YTkyNzctMjc3Yy03MzJhLThlYzgtNTZjMDMxMzM4OTAyOjViM2I1OTNiLTkwZTMtNGE5Yy1iYTJiLWM1YjhiYTRiM2E1Yg==
GIGACHAT_CLIENT_ID=019a9277-277c-732a-8ec8-56c031338902
GIGACHAT_CLIENT_SECRET=5b3b593b-90e3-4a9c-ba2b-c5b8ba4b3a5b
```

**Option 2: Fix GIGACHAT_CREDENTIALS Format**

If you want to use `GIGACHAT_CREDENTIALS`, ensure it's correctly base64-encoded:

```python
import base64

client_id = "your_client_id"
client_secret = "your_client_secret"

# Correct format: client_id:client_secret
credentials = f"{client_id}:{client_secret}"
encoded = base64.b64encode(credentials.encode()).decode()

print(f"GIGACHAT_CREDENTIALS={encoded}")
```

## Verification

After fixing, test authentication:

```bash
python3 scripts/test_current_model.py
```

Expected output:
```
✓ Model is available
✓ Test successful!
```

## Authentication Flow

### Using CLIENT_ID/SECRET (Recommended)
```
1. Read GIGACHAT_CLIENT_ID and GIGACHAT_CLIENT_SECRET from .env
2. Combine as "client_id:client_secret"
3. Base64 encode
4. Add "Basic " prefix
5. Send to OAuth endpoint
```

### Using GIGACHAT_CREDENTIALS
```
1. Read GIGACHAT_CREDENTIALS from .env (already base64-encoded)
2. Add "Basic " prefix
3. Send to OAuth endpoint
```

## Why CLIENT_ID/SECRET is Better

1. **Clearer**: Separate values are easier to understand
2. **Safer**: Less chance of encoding errors
3. **Standard**: Matches OAuth2 best practices
4. **Debuggable**: Can verify each part separately

## Testing Different Methods

### Test with CLIENT_ID/SECRET
```bash
# Ensure GIGACHAT_CREDENTIALS is commented out in .env
python3 scripts/test_current_model.py
```

### Test with GIGACHAT_CREDENTIALS
```bash
# Uncomment GIGACHAT_CREDENTIALS in .env
# Comment out CLIENT_ID and CLIENT_SECRET
python3 scripts/test_current_model.py
```

## Other Authentication Issues

### Rate Limiting (429 Error)
```
ERROR | GigaChat auth failed: 429 - Too Many Requests
```

**Solution**: Wait 1-5 minutes before retrying. See `docs/STRESS_TESTING_RATE_LIMITS.md`.

### Invalid Credentials (401 Error)
```
ERROR | GigaChat auth failed: 401 - Unauthorized
```

**Solution**: Verify your credentials are correct in the GigaChat console.

### Network Issues
```
ERROR | Cannot connect to GigaChat API
```

**Solution**: 
- Check internet connection
- Verify firewall settings
- Check if GigaChat API is accessible

## Configuration Priority

The provider checks credentials in this order:

1. Constructor parameters (if provided)
2. `GIGACHAT_CREDENTIALS` environment variable
3. `GIGACHAT_CLIENT_ID` + `GIGACHAT_CLIENT_SECRET` environment variables

## Recommended .env Configuration

```bash
# GigaChat Authentication (use CLIENT_ID/SECRET method)
GIGACHAT_CLIENT_ID=your_client_id_here
GIGACHAT_CLIENT_SECRET=your_client_secret_here
GIGACHAT_SCOPE=GIGACHAT_API_PERS

# Optional: Pre-encoded credentials (not recommended)
# GIGACHAT_CREDENTIALS=base64_encoded_credentials_here
```

## Quick Fix Script

If you're still having issues, run this to regenerate credentials:

```python
import base64
import os

# Read from .env
client_id = os.getenv("GIGACHAT_CLIENT_ID")
client_secret = os.getenv("GIGACHAT_CLIENT_SECRET")

if client_id and client_secret:
    # Generate correct GIGACHAT_CREDENTIALS
    creds = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(creds.encode()).decode()
    print(f"GIGACHAT_CREDENTIALS={encoded}")
else:
    print("CLIENT_ID or CLIENT_SECRET not found in environment")
```

## Summary

**Problem**: `GIGACHAT_CREDENTIALS` in .env causing "Can't decode 'Authorization' header" error

**Solution**: Comment out `GIGACHAT_CREDENTIALS` and use `GIGACHAT_CLIENT_ID` + `GIGACHAT_CLIENT_SECRET` instead

**Verification**: Run `python3 scripts/test_current_model.py` to confirm it works
