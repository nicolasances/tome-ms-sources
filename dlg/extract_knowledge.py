import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from pymongo.auth import authenticate
import requests
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import authentication
from config.prompts import get_prompt
from langchain_aws import ChatBedrock
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymongo import MongoClient
from totoms.TotoLogger import TotoLogger
from totoms.TotoDelegateDecorator import toto_delegate
from totoms.model import ExecutionContext, UserContext

from dlg.fetchers import FETCHER_REGISTRY
from store.sources_store import SourcesStore

MAX_CONTENT_CHARS = 500_000
CHUNK_THRESHOLD_CHARS = 100_000
CHUNK_SIZE_TOKENS = 3_000
CHUNK_OVERLAP_TOKENS = 200


@toto_delegate
async def extract_knowledge(request: Request, user_context: UserContext, exec_context: ExecutionContext):
    source_id = request.path_params.get("sourceId")
    config = exec_context.config

    # ── Validate sourceId ──────────────────────────────────────────────────────
    try:
        ObjectId(source_id)
    except (InvalidId, TypeError):
        return JSONResponse(content={"message": f"Invalid sourceId: '{source_id}'"}, status_code=400)

    # ── Connect to MongoDB ─────────────────────────────────────────────────────
    with MongoClient(
        host=config.mongo_host,
        username=config.mongo_user,
        password=config.mongo_pwd,
        authSource=config.get_db_name(),
    ) as client:
        db = client[config.get_db_name()]
        store = SourcesStore(db, config)

        # ── Step 1: Load the source + ownership check ──────────────────────────────
        source = store.find_source_by_id(source_id)
        
        # Commented out this check for now .. 
        # if source is None or source.user_id != user_context.email:
        #     return JSONResponse(content={"message": "Source not found"}, status_code=404)

        # ── Step 2: Fetch content ──────────────────────────────────────────────────
        fetcher_cls = FETCHER_REGISTRY.get(source.type)
        if fetcher_cls is None:
            return JSONResponse(
                content={"message": f"No fetcher registered for source type '{source.type}'"},
                status_code=502,
            )

        try:
            # Fetch
            content: str = fetcher_cls().fetch(source.to_bson())
            
        except Exception as exc:
            logging.warning("Failed to fetch source content for source %s: %s", source_id, exc)
            
            return JSONResponse(content={"message": "Failed to fetch source content"}, status_code=502)

        if not content:
            return JSONResponse(
                content={"sourceId": source_id, "wordsExtracted": 0, "wordsCreated": 0, "wordsErrored": 0},
                status_code=200,
            )

        if len(content) > MAX_CONTENT_CHARS:
            return JSONResponse(
                content={"message": f"Source content exceeds the {MAX_CONTENT_CHARS:,}-character limit"},
                status_code=400,
            )

        # ── Step 3: LLM extraction ─────────────────────────────────────────────────
        chunks = _split_content(content)
        all_pairs, all_failed = _extract_from_chunks(chunks, source.language, config)

        if all_failed and len(chunks) > 0:
            return JSONResponse(
                content={"message": "LLM extraction failed for all chunks after retries"},
                status_code=502,
            )

        # Deduplicate (case-insensitive on both fields)
        deduped = _deduplicate(all_pairs)

        if not deduped:
            return JSONResponse(
                content={"sourceId": source_id, "wordsExtracted": 0, "wordsCreated": 0, "wordsErrored": 0},
                status_code=200,
            )
            
        print(f"Extracted {len(all_pairs)} total pairs, {len(deduped)} after deduplication")
        print(f"Sample extracted pairs: {deduped[:5]}")

        # ── Step 4: POST to tome-ms-language ──────────────────────────────────────
        # auth_header = request.headers.get("Authorization", "")
        # correlation_id = exec_context.cid

        # lang_response = _post_to_language_service(
        #     config=config,
        #     language=source.language,
        #     words=deduped,
        #     auth_header=auth_header,
        #     correlation_id=correlation_id,
        # )
        # if isinstance(lang_response, JSONResponse):
        #     return lang_response

        # words_created, words_errored = lang_response

        # ── Step 5: Update lastExtractedAt ─────────────────────────────────────────
        # timestamp = datetime.now(timezone.utc).isoformat()
        # store.update_last_extracted_at(source_id, timestamp)

    return JSONResponse(
        content={
            "sourceId": source_id,
            "wordsExtracted": len(deduped),
            # "wordsCreated": words_created,
            # "wordsErrored": words_errored,
        },
        status_code=200,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _split_content(content: str) -> List[str]:
    """Return a list of text chunks. Single chunk when content ≤ threshold."""
    if len(content) <= CHUNK_THRESHOLD_CHARS:
        return [content]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_TOKENS * 4,   # ~4 chars per token
        chunk_overlap=CHUNK_OVERLAP_TOKENS * 4,
    )
    return splitter.split_text(content)


def _create_llm(hyperscaler: str):
    """Create the appropriate LLM based on the hyperscaler."""
    logger = TotoLogger.get_instance()
    provider = hyperscaler.lower()

    if provider == "gcp":
        project = os.environ.get("GCP_PID")
        location = os.environ.get("GCP_REGION", "europe-west1")
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

        logger.log("LLM", f"Creating Google Gemini LLM with model: {model}, project: {project}, location: {location}")

        return ChatGoogleGenerativeAI(
            model=model,
            project=project,
            location=location,
            temperature=0,
            thinking_budget=-1,  # -1 means dynamic/unlimited thinking budget (model decides)
            include_thoughts=True,
        )

    if provider == "aws":
        model_id = os.environ.get("BEDROCK_MODEL_ID", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0")
        aws_region = os.environ.get("AWS_REGION", "eu-north-1")

        logger.log("LLM", f"Creating AWS Bedrock LLM with model: {model_id}, region: {aws_region}")

        return ChatBedrock(
            model_id=model_id,
            region_name=aws_region,
            model_kwargs={
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 4096,  # max tokens Claude may spend on internal reasoning
                },
            },
        )

    raise ValueError(f"Unsupported HYPERSCALER '{hyperscaler}'. Use 'aws' or 'gcp'.")


def _extract_from_chunks(
    chunks: List[str],
    language: str,
    config,
) -> Tuple[List[dict], bool]:
    """
    Run LLM extraction over every chunk.

    Returns:
        (all_pairs, all_failed) where all_failed is True only when every chunk
        failed after its retry.
    """
    all_pairs: List[dict] = []
    failed_count = 0

    llm = _create_llm(config.environment.hyperscaler)

    for chunk in chunks:
        pairs = _extract_chunk_with_retry(chunk, language, config, llm)
        if pairs is None:
            failed_count += 1
        else:
            all_pairs.extend(pairs)

    all_failed = failed_count == len(chunks)
    return all_pairs, all_failed


def _extract_chunk_with_retry( chunk: str, language: str, config, llm, max_attempts: int = 2, ) -> Optional[List[dict]]:
    """
    Call the LLM for a single chunk with up to *max_attempts* attempts.
    Returns a (possibly empty) list of valid word-pair dicts, or None on failure.
    """
    prompt = get_prompt("extraction").format(text=chunk)

    for attempt in range(max_attempts):
        try:
            response = llm.invoke([{"role": "user", "content": prompt}])
            
            raw = _extract_text_from_response(response)
            
            data = _parse_json(raw)
            
            words = data.get("words", [])
            
            # Validate and filter entries
            valid = [
                {"english": w["english"], "translation": w["translation"]}
                for w in words
                if isinstance(w, dict)
                and w.get("english") and w.get("translation")
                and isinstance(w["english"], str) and isinstance(w["translation"], str)
                and w["english"].strip() and w["translation"].strip()
            ]
        
            return valid
        
        except Exception as exc:
            logging.warning(
                "LLM extraction attempt %d/%d failed: %s", attempt + 1, max_attempts, exc
            )
            if attempt < max_attempts - 1:
                continue
    return None


def _extract_text_from_response(response) -> str:
    """
    Extract the final text answer from an LLM response.

    Thinking models (Gemini with include_thoughts, Bedrock with thinking enabled)
    return a list of content parts. Only "text" parts (not "thinking") are included
    in the final answer.
    """
    content = response.content if hasattr(response, "content") else str(response)
    
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    
    return str(content)


def _parse_json(text: str) -> dict:
    """
    Parse a JSON object from model output.

    Strips markdown code fences if present, then attempts a direct parse.
    Falls back to extracting the first JSON object found in the text.
    """
    text = text.strip()
    # Strip markdown code fences (e.g. ```json ... ```)
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text.strip())
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def _deduplicate(pairs: List[dict]) -> List[dict]:
    """Remove duplicate (english, translation) pairs (case-insensitive)."""
    seen = set()
    result = []
    for pair in pairs:
        key = (pair["english"].lower(), pair["translation"].lower())
        if key not in seen:
            seen.add(key)
            result.append(pair)
    return result


def _post_to_language_service(
    config,
    language: str,
    words: List[dict],
    auth_header: str,
    correlation_id: str,
) -> "Tuple[int, int] | JSONResponse":
    """
    POST words to tome-ms-language. Returns (words_created, words_errored) on
    success (207), or a JSONResponse with status 502 on failure.
    """
    url = f"{config.tome_language_url}/tomelang/vocabulary/{language}/words/batch"
    headers = {
        "Authorization": auth_header,
        "x-correlation-id": correlation_id,
        "Content-Type": "application/json",
    }
    payload = {"words": words}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
    except Exception as exc:
        logging.warning("tome-ms-language unreachable at %s: %s", url, exc)
        return JSONResponse(
            content={"message": "Failed to communicate with tome-ms-language service"},
            status_code=502,
        )

    if resp.status_code != 207:
        detail = resp.text[:500] if resp.text else "(no body)"
        return JSONResponse(
            content={
                "message": f"tome-ms-language returned unexpected status {resp.status_code}",
                "detail": detail,
            },
            status_code=502,
        )

    resp_data = resp.json()
    words_created = sum(1 for w in resp_data.get("words", []) if w.get("status") == "created")
    words_errored = sum(1 for w in resp_data.get("words", []) if w.get("status") == "error")
    return words_created, words_errored
