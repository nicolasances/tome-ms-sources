import asyncio
import os
from totoms.model.TotoConfig import TotoControllerConfig
from typing import Optional, Dict, List

SUPPORTED_TYPES: List[str] = ["google_doc"]
SUPPORTED_LANGUAGES: List[str] = ["danish"]

# LLM defaults — can be overridden via environment variables
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY_SECRET: str = os.getenv("LLM_API_KEY_SECRET", "openai-api-key")

# Prompt for vocabulary extraction — stored here to allow tuning without code changes
EXTRACTION_PROMPT: str = (
    "You are a language learning assistant. "
    "Read the following text and extract every word or short phrase that is written in the target language "
    "(not in English), along with its English meaning. "
    "Return a JSON object with a single key 'words' whose value is a list of objects, "
    "each having 'english' (the English meaning) and 'translation' (the target-language word or phrase). "
    "Only include entries where both fields are non-empty strings. "
    "Do not include any other text outside the JSON object.\n\n"
    "Text:\n{text}"
)


class MyConfig(TotoControllerConfig):
    """Custom configuration for the tome-ms-sources service."""

    def __init__(self, environment):
        super().__init__(environment)
        self._llm_api_key: Optional[str] = None
        self._tome_language_url: Optional[str] = None

    async def load(self) -> "MyConfig":
        await super().load()

        # Load LLM API key from secrets manager
        self._llm_api_key = await asyncio.to_thread(
            self.secrets_manager.get_secret, LLM_API_KEY_SECRET
        )

        # TOME_LANGUAGE_URL can come from an env var or fall back to a secret
        self._tome_language_url = os.getenv("TOME_LANGUAGE_URL") or await asyncio.to_thread(
            self.secrets_manager.get_secret, "tome-language-url"
        )

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
    def llm_provider(self) -> str:
        """Return the LLM provider name."""
        return LLM_PROVIDER

    @property
    def llm_model(self) -> str:
        """Return the LLM model name."""
        return LLM_MODEL

    @property
    def llm_api_key(self) -> Optional[str]:
        """Return the LLM API key loaded from secrets manager."""
        return self._llm_api_key

    @property
    def extraction_prompt(self) -> str:
        """Return the vocabulary extraction prompt template."""
        return EXTRACTION_PROMPT

    @property
    def tome_language_url(self) -> Optional[str]:
        """Return the base URL of the tome-ms-language service."""
        return self._tome_language_url
