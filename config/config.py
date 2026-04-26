from totoms.model.TotoConfig import TotoControllerConfig
from typing import Optional, Dict, List

SUPPORTED_TYPES: List[str] = ["google_doc"]
SUPPORTED_LANGUAGES: List[str] = ["danish"]

class MyConfig(TotoControllerConfig):
    """Custom configuration for the tome-ms-sources service."""

    def get_mongo_secret_names(self) -> Optional[Dict[str, str]]:
        """Return MongoDB secret names for this service."""
        return {
            "user_secret_name": "tome-ms-sources-mongo-user",
            "pwd_secret_name": "tome-ms-sources-mongo-pswd",
        }

    @property
    def supported_types(self) -> List[str]:
        """Return the list of supported source types."""
        return SUPPORTED_TYPES

    @property
    def supported_languages(self) -> List[str]:
        """Return the list of supported target languages."""
        return SUPPORTED_LANGUAGES
