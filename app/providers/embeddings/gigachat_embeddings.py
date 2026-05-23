import asyncio
import logging
from functools import cached_property
from typing import List, Optional

from langchain_gigachat.embeddings import GigaChatEmbeddings as LangChainGigaChatEmbeddings

from app.core.config import settings
from app.interfaces.embeddings_provider import IEmbeddingsProvider

logger = logging.getLogger(__name__)


class GigaChatEmbeddings(IEmbeddingsProvider):
    """Embeddings provider backed by langchain-gigachat SDK.

    Uses the SDK's built-in SSL handling with Russian trusted root certificates,
    so no manual certificate management or verify=False is needed.
    """

    @cached_property
    def _client(self) -> LangChainGigaChatEmbeddings:
        credentials = settings.GIGACHAT_CREDENTIALS or None
        scope = settings.GIGACHAT_SCOPE or "GIGACHAT_API_PERS"
        
        from app.core.ssl_utils import get_ca_bundle_path
        ca_bundle = get_ca_bundle_path()

        if not credentials:
            raise ValueError("GIGACHAT_CREDENTIALS must be provided for embeddings")

        client_kwargs = {
            "credentials": credentials,
            "scope": scope,
            "verify_ssl_certs": True,
        }
        
        if ca_bundle:
            # SDK supports ca_bundle_file parameter to explicitly point to Russian CA certs
            client_kwargs["ca_bundle_file"] = ca_bundle
            logger.info(f"GigaChatEmbeddings using CA bundle file: {ca_bundle}")
        else:
            logger.warning("No CA bundle found, relying on SDK default SSL handling")

        client = LangChainGigaChatEmbeddings(**client_kwargs)
        logger.info("GigaChatEmbeddings client initialized via langchain-gigachat SDK")
        return client

    async def embed_query(self, text: str, instruction: Optional[str] = None) -> List[float]:
        return await asyncio.get_event_loop().run_in_executor(
            None, self._client.embed_query, text
        )

    async def embed_documents(self, texts: List[str], instruction: Optional[str] = None) -> List[List[float]]:
        return await asyncio.get_event_loop().run_in_executor(
            None, self._client.embed_documents, texts
        )
