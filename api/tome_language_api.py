from typing import List, Tuple

from fastapi.responses import JSONResponse
from totoms import TotoLogger
from agent.extraction_agent import Word
from config.config import MyConfig

import requests

def post_words( config: MyConfig, language: str, words: List[Word], auth_header: str, correlation_id: str) -> Tuple[int, int]:
    """
    POST words to tome-ms-language. 
    Returns (words_created, words_errored) on
    success (207), or a JSONResponse with status 502 on failure.
    """
    logger = TotoLogger.get_instance()
    
    url = f"{config.tome_language_url}/tomelang/vocabulary/{language}/words/batch"
    
    headers = {
        "Authorization": auth_header,
        "x-correlation-id": correlation_id,
        "Content-Type": "application/json",
    }
    
    payload = {"words": words}

    try:
        logger.log(correlation_id, f"Posting {len(words)} words to Tome Language API")
        
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        
        logger.log(correlation_id, f"Successfully posted {len(words)} to Tome Language API")
        
    except Exception as exc:
        
        print(exc)
        raise exc
        

    resp_data = resp.json()
    
    words_created = sum(1 for w in resp_data.get("words", []) if w.get("status") == "created")
    words_errored = sum(1 for w in resp_data.get("words", []) if w.get("status") == "error")
    
    return (words_created, words_errored)