import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Request
from fastapi.responses import JSONResponse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pymongo import MongoClient
from totoms.TotoLogger import TotoLogger
from totoms.TotoDelegateDecorator import toto_delegate
from totoms.model import ExecutionContext, UserContext

from api.tome_language_api import post_words, post_sentences
from config.config import MyConfig
from dlg.fetchers import FETCHER_REGISTRY
from dlg.word_extractor import extract_words
from dlg.sentence_extractor import extract_sentences, verify_sentences
from store.sources_store import SourcesStore

MAX_CONTENT_CHARS = 500_000
CHUNK_THRESHOLD_CHARS = 100_000
CHUNK_SIZE_TOKENS = 3_000
CHUNK_OVERLAP_TOKENS = 200


@toto_delegate
async def extract_knowledge(request: Request, user_context: UserContext, exec_context: ExecutionContext):
    source_id = request.path_params.get("sourceId")
    config: MyConfig = exec_context.config  # type: ignore

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
            content: str = fetcher_cls().fetch(source.to_bson())
        except Exception as exc:
            logging.warning("Failed to fetch source content for source %s: %s", source_id, exc)
            return JSONResponse(content={"message": "Failed to fetch source content"}, status_code=502)

        if not content:
            return JSONResponse(
                content={
                    "sourceId": source_id,
                    "wordsExtracted": 0, "wordsCreated": 0, "wordsErrored": 0,
                    "sentencesExtracted": 0, "sentencesCreated": 0, "sentencesErrored": 0,
                },
                status_code=200,
            )

        if len(content) > MAX_CONTENT_CHARS:
            return JSONResponse(
                content={"message": f"Source content exceeds the {MAX_CONTENT_CHARS:,}-character limit"},
                status_code=400,
            )

        # ── Steps 3 & 4: Parallel LLM extraction ──────────────────────────────────
        chunks = _split_content(content)

        (deduped_words, words_all_failed), (deduped_sentences, _) = await asyncio.gather(
            extract_words(chunks, source.language, config),
            extract_sentences(chunks, source.language, config),
        )

        logger = TotoLogger.get_instance()
        logger.log("", f"Extracted {len(deduped_words)} words, {len(deduped_sentences)} sentences")

        if words_all_failed and len(chunks) > 0:
            return JSONResponse(
                content={"message": "LLM extraction failed for all chunks after retries"},
                status_code=502,
            )

        # ── Step 5: Verify extracted sentences ────────────────────────────────────
        correlation_id = exec_context.cid
        deduped_sentences = await verify_sentences(deduped_sentences, config, correlation_id)

        # ── Step 6: POST vocabulary to tome-ms-language ───────────────────────────
        auth_header = request.headers.get("Authorization", "")

        words_created = 0
        words_errored = 0
        if deduped_words:
            words_created, words_errored = post_words(
                config, source.language, deduped_words, source_id, auth_header, correlation_id
            )

        # ── Step 7: POST sentences to tome-ms-language (non-fatal on failure) ─────
        sentences_created = 0
        sentences_errored = 0
        if deduped_sentences:
            try:
                sentence_dicts = [{"sentence": s.sentence, "translation": s.translation} for s in deduped_sentences]
                sentences_created, sentences_errored = post_sentences(
                    config, source.language, sentence_dicts, source_id, auth_header, correlation_id
                )
            except Exception as exc:
                logger.log(correlation_id, f"Failed to post sentences (non-fatal): {exc}")
                sentences_errored = len(deduped_sentences)

        # ── Step 8: Update lastExtractedAt ────────────────────────────────────────
        timestamp = datetime.now(timezone.utc).isoformat()
        store.update_last_extracted_at(source_id, timestamp)

    return JSONResponse(
        content={
            "sourceId": source_id,
            "wordsExtracted": len(deduped_words),
            "wordsCreated": words_created,
            "wordsErrored": words_errored,
            "sentencesExtracted": len(deduped_sentences),
            "sentencesCreated": sentences_created,
            "sentencesErrored": sentences_errored,
        },
        status_code=200,
    )


def _split_content(content: str) -> List[str]:
    """Return a list of text chunks. Single chunk when content ≤ threshold."""
    if len(content) <= CHUNK_THRESHOLD_CHARS:
        return [content]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_TOKENS * 4,   # ~4 chars per token
        chunk_overlap=CHUNK_OVERLAP_TOKENS * 4,
    )
    return splitter.split_text(content)
