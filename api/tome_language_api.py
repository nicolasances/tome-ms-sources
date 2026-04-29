import os
from typing import List, Tuple

from fastapi.responses import JSONResponse
from totoms import TotoLogger
from agent.extraction_agent import Word
from config.config import MyConfig

import requests

# Use custom CA bundle if specified, otherwise use default (True)
SSL_CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE", True)

def post_words( config: MyConfig, language: str, words: List[Word], source_id: str, auth_header: str, correlation_id: str) -> Tuple[int, int]:
    """
    POST words to tome-ms-language. 
    Returns (words_created, words_errored) on
    success (207), or a JSONResponse with status 502 on failure.
    """
    logger = TotoLogger.get_instance()
    
    url = f"{config.tome_language_url}/vocabulary/{language}/words/batch"
    
    headers = {
        "Authorization": auth_header,
        "x-correlation-id": correlation_id,
        "Content-Type": "application/json",
    }
    
    # Add knowledgeSource to each word before sending
    payload = {"words": [{**w.model_dump(), "knowledgeSource": source_id} for w in words]}

    try:
        logger.log(correlation_id, f"Posting {len(words)} words to Tome Language API")
        
        resp = requests.post(url, json=payload, headers=headers, timeout=30, verify=False)
        
        logger.log(correlation_id, f"Successfully posted {len(words)} to Tome Language API")
        
    except Exception as exc:
        
        print(exc)
        raise exc
        

    resp_data = resp.json()
    
    words_created = sum(1 for w in resp_data.get("results", []) if w.get("status") == "created")
    words_errored = sum(1 for w in resp_data.get("results", []) if w.get("status") == "error")
    
    return (words_created, words_errored)