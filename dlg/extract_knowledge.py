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
from agent.extraction_agent import KnowledgeExtractionAgent, Word
from agent.sentence_extraction_agent import SentenceExtractionAgent, SentencePair
from api.tome_language_api import post_words, post_sentences
from config.config import MyConfig
from config.prompts import get_prompt
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
    config: MyConfig = exec_context.config # type: ignore
    
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
                content={"sourceId": source_id, "wordsExtracted": 0, "wordsCreated": 0, "wordsErrored": 0,
                         "sentencesExtracted": 0, "sentencesCreated": 0, "sentencesErrored": 0},
                status_code=200,
            )

        if len(content) > MAX_CONTENT_CHARS:
            return JSONResponse(
                content={"message": f"Source content exceeds the {MAX_CONTENT_CHARS:,}-character limit"},
                status_code=400,
            )

        # ── Step 3: LLM vocabulary extraction ─────────────────────────────────────
        chunks = _split_content(content)
        
        all_pairs, all_failed = await _extract_words_from_chunks(chunks, source.language, config)
        
        logger = TotoLogger.get_instance()
        logger.log("", f"Extracted {len(all_pairs)} total pairs")


        if all_failed and len(chunks) > 0:
            return JSONResponse(
                content={"message": "LLM extraction failed for all chunks after retries"},
                status_code=502,
            )

        # Deduplicate (case-insensitive on both fields)
        deduped = _deduplicate(all_pairs)

        print(f"Extracted {len(all_pairs)} total pairs, {len(deduped)} after deduplication")
        print(f"Sample extracted pairs: {deduped[:5]}")

        # ── Step 4: LLM sentence extraction ───────────────────────────────────────
        all_sentence_pairs, sentences_all_failed = await _extract_sentences_from_chunks(chunks, source.language, config)
        deduped_sentences = _deduplicate_sentences(all_sentence_pairs)
        logger.log("", f"Extracted {len(deduped_sentences)} sentences after deduplication")

        # ── Step 5: POST vocabulary to tome-ms-language ────────────────────────────
        auth_header = request.headers.get("Authorization", "")
        correlation_id = exec_context.cid

        words_created = 0
        words_errored = 0
        if deduped:
            words_created, words_errored = post_words(config, "danish", deduped, source_id, auth_header, correlation_id)

        # ── Step 6: POST sentences to tome-ms-language (non-fatal on failure) ──────
        sentences_created = 0
        sentences_errored = 0
        if deduped_sentences:
            try:
                sentence_dicts = [{"sentence": s.sentence, "translation": s.translation} for s in deduped_sentences]
                sentences_created, sentences_errored = post_sentences(
                    config, "danish", sentence_dicts, source_id, auth_header, correlation_id
                )
            except Exception as exc:
                logger.log(correlation_id, f"Failed to post sentences (non-fatal): {exc}")
                sentences_errored = len(deduped_sentences)

        # ── Step 7: Update lastExtractedAt ─────────────────────────────────────────
        timestamp = datetime.now(timezone.utc).isoformat()
        store.update_last_extracted_at(source_id, timestamp)

    return JSONResponse(
        content={
            "sourceId": source_id,
            "wordsExtracted": len(deduped),
            "wordsCreated": words_created,
            "wordsErrored": words_errored,
            "sentencesExtracted": len(deduped_sentences),
            "sentencesCreated": sentences_created,
            "sentencesErrored": sentences_errored,
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


async def _extract_words_from_chunks( chunks: List[str], language: str, config, ) -> Tuple[List[Word], bool]:
    """
    Run LLM extraction over every chunk.

    Returns:
        (all_pairs, all_failed) where all_failed is True only when every chunk
        failed after its retry.
    """
    all_pairs: List[Word] = []
    failed_count = 0
    
    agent = KnowledgeExtractionAgent(config)

    for chunk in chunks:
        
        words = await _extract_chunk_with_retry(chunk, language, config, agent)
        
        if words is None:
            failed_count += 1
        else:
            all_pairs.extend(words)

    all_failed = failed_count == len(chunks)
    return all_pairs, all_failed


async def _extract_chunk_with_retry( chunk: str, language: str, config, agent: KnowledgeExtractionAgent, max_attempts: int = 2, ) -> Optional[List[Word]]:
    """
    Call the LLM for a single chunk with up to *max_attempts* attempts.
    Returns a (possibly empty) list of valid word-pair dicts, or None on failure.
    """
    logger = TotoLogger.get_instance()
    
    for attempt in range(max_attempts):
        try:
            logger.log("", f"LLM extraction attempt {attempt + 1}/{max_attempts} for chunk (first 500 chars): {chunk[:500]!r}")
            
            words = await agent._extract_knowledge_from_chunk(chunk)
            
            return words.words
        
        except Exception as exc:
            
            logging.warning( "LLM extraction attempt %d/%d failed: %s", attempt + 1, max_attempts, exc )
            
            if attempt < max_attempts - 1:
                continue
            
    return None


def _deduplicate(pairs: List[Word]) -> List[Word]:
    """Remove duplicate (english, translation) pairs (case-insensitive)."""
    seen = set()
    result = []
    for pair in pairs:
        key = (pair.english.lower(), pair.translation.lower())
        if key not in seen:
            seen.add(key)
            result.append(pair)
    return result


async def _extract_sentences_from_chunks(
    chunks: List[str], language: str, config
) -> Tuple[List[SentencePair], bool]:
    """
    Run sentence extraction over every chunk.
    Returns (all_sentence_pairs, all_failed).
    """
    all_pairs: List[SentencePair] = []
    failed_count = 0

    agent = SentenceExtractionAgent(config)

    for chunk in chunks:
        try:
            result = await agent.extract(chunk)
            all_pairs.extend(result.sentences)
        except Exception as exc:
            logging.warning("Sentence extraction failed for chunk: %s", exc)
            failed_count += 1

    all_failed = failed_count == len(chunks) and len(chunks) > 0
    return all_pairs, all_failed


def _deduplicate_sentences(pairs: List[SentencePair]) -> List[SentencePair]:
    """Remove duplicate sentences (case-insensitive on the Danish sentence)."""
    seen: set = set()
    result = []
    for pair in pairs:
        key = pair.sentence.lower()
        if key not in seen:
            seen.add(key)
            result.append(pair)
    return result


