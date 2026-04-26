from totoms.model.TotoConfig import TotoControllerConfig
from typing import Optional, Dict

class MyConfig(TotoControllerConfig):
    """Custom configuration for the Toto Toto Ex1 service."""
    
    def get_mongo_secret_names(self) -> Optional[Dict[str, str]]:
        """Return MongoDB secret names if service uses MongoDB."""
        return None
