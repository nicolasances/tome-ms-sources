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
        

    try: 
        resp_data = resp.json()
        
        words_created = sum(1 for w in resp_data.get("results", []) if w.get("status") == "created")
        words_errored = sum(1 for w in resp_data.get("results", []) if w.get("status") == "error")
    
        return (words_created, words_errored)
        
    except Exception as e: 
        
        print(e)
        print(resp)
        return (0, len(words))


def post_sentences(
    config: MyConfig,
    language: str,
    sentences: List[dict],
    knowledge_source: str,
    auth_header: str,
    correlation_id: str,
) -> Tuple[int, int]:
    """
    POST sentences to tome-ms-language's batch endpoint.
    Returns (sentences_created, sentences_errored).
    Raises an exception if the service is unreachable.
    Does NOT raise on non-207 status — the caller decides how to handle that.
    """
    logger = TotoLogger.get_instance()

    url = f"{config.tome_language_url}/sentences/{language}/batch"

    headers = {
        "Authorization": auth_header,
        "x-correlation-id": correlation_id,
        "Content-Type": "application/json",
    }

    payload = {
        "sentences": [
            {
                "sentence": s["sentence"],
                "translation": s["translation"],
                "knowledgeSource": knowledge_source,
            }
            for s in sentences
        ]
    }

    logger.log(correlation_id, f"Posting {len(sentences)} sentences to Tome Language API")
    resp = requests.post(url, json=payload, headers=headers, timeout=30, verify=False)
    logger.log(correlation_id, f"Sentences POST response status: {resp.status_code}")

    try:
        resp_data = resp.json()
        created = sum(1 for r in resp_data.get("results", []) if r.get("status") == "created")
        errored = sum(1 for r in resp_data.get("results", []) if r.get("status") == "error")
        return (created, errored)
    except Exception as e:
        print(e)
        return (0, len(sentences))


def sample_words(
    config: MyConfig,
    language: str,
    n: int,
    auth_header: str,
    correlation_id: str,
) -> List[dict]:
    """
    GET a random sample of n vocabulary words from tome-ms-language.
    Returns a list of word dicts. Raises on network error.
    """
    logger = TotoLogger.get_instance()

    url = f"{config.tome_language_url}/vocabulary/{language}/words/sample?n={n}"

    headers = {
        "Authorization": auth_header,
        "x-correlation-id": correlation_id,
    }

    logger.log(correlation_id, f"Sampling {n} words from Tome Language API")
    resp = requests.get(url, headers=headers, timeout=15, verify=False)
    resp.raise_for_status()

    data = resp.json()
    words = data.get("words", [])
    logger.log(correlation_id, f"Sampled {len(words)} words")
    return words