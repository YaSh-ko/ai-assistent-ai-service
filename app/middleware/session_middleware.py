from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import logging

logger = logging.getLogger(__name__)

class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        session_id = request.headers.get("X-Session-ID")
        
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"Generated new session_id: {session_id} for request to {request.url.path}")
            # In a real app, we might want to inject this into the request state
            # request.state.session_id = session_id
        else:
            # Basic validation (optional, e.g. check UUID format)
            try:
                uuid.UUID(session_id)
            except ValueError:
                logger.warning(f"Invalid X-Session-ID header format: {session_id}. Generating new one.")
                session_id = str(uuid.uuid4())

        response = await call_next(request)
        response.headers["X-Session-ID"] = session_id
        return response
