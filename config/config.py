import asyncio
import os
from totoms.model.TotoConfig import TotoControllerConfig
from typing import Optional, Dict, List

SUPPORTED_TYPES: List[str] = ["google_doc"]
SUPPORTED_LANGUAGES: List[str] = ["danish"]


class MyConfig(TotoControllerConfig):
    """Custom configuration for the tome-ms-sources service."""

    def __init__(self, environment):
        super().__init__(environment)
        self._tome_language_url: Optional[str] = None

    async def load(self) -> "MyConfig":
        await super().load()

        # TOME_LANGUAGE_URL can come from an env var or fall back to a secret
        self._tome_language_url = os.getenv("TOME_LANGUAGE_API_ENDPOINT")
        
        return self

    def get_mongo_secret_names(self) -> Optional[Dict[str, str]]:
        """Return MongoDB secret names for this service."""
        return {
            "user_secret_name": "tome-ms-sources-mongo-user",
            "pwd_secret_name": "tome-ms-sources-mongo-pswd",
        }

    def get_db_name(self) -> str:
        """Return the MongoDB database name for this service."""
        return "tomesources"

    @property
    def supported_types(self) -> List[str]:
        """Return the list of supported source types."""
        return SUPPORTED_TYPES

    @property
    def supported_languages(self) -> List[str]:
        """Return the list of supported target languages."""
        return SUPPORTED_LANGUAGES

    @property
    def tome_language_url(self) -> Optional[str]:
        """Return the base URL of the tome-ms-language service."""
        return self._tome_language_url
