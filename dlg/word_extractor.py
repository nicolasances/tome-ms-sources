"""
Utility module for extracting vocabulary (word-translation pairs) from text chunks using LLM.
"""
import logging
from typing import List, Optional, Tuple

from agent.extraction_agent import KnowledgeExtractionAgent, Word
from totoms.TotoLogger import TotoLogger


async def extract_words(
    chunks: List[str], language: str, config
) -> Tuple[List[Word], bool]:
    """
    Extract and deduplicate vocabulary pairs from all chunks via LLM.

    Returns:
        (deduped_words, all_failed) — all_failed is True only when every
        chunk failed after its retry.
    """
    agent = KnowledgeExtractionAgent(config)
    all_pairs: List[Word] = []
    failed_count = 0

    for chunk in chunks:
        words = await _extract_chunk_with_retry(chunk, language, config, agent)
        if words is None:
            failed_count += 1
        else:
            all_pairs.extend(words)

    all_failed = failed_count == len(chunks) and len(chunks) > 0
    return _deduplicate(all_pairs), all_failed


async def _extract_chunk_with_retry(
    chunk: str,
    language: str,
    config,
    agent: KnowledgeExtractionAgent,
    max_attempts: int = 2,
) -> Optional[List[Word]]:
    """
    Call the LLM for a single chunk with up to *max_attempts* attempts.
    Returns a (possibly empty) list of Word objects, or None on failure.
    """
    logger = TotoLogger.get_instance()

    for attempt in range(max_attempts):
        try:
            logger.log(
                "",
                f"Word extraction attempt {attempt + 1}/{max_attempts} "
                f"for chunk (first 500 chars): {chunk[:500]!r}",
            )
            result = await agent._extract_knowledge_from_chunk(chunk)
            return result.words

        except Exception as exc:
            logging.warning(
                "Word extraction attempt %d/%d failed: %s",
                attempt + 1,
                max_attempts,
                exc,
            )
            if attempt < max_attempts - 1:
                continue

    return None


def _deduplicate(pairs: List[Word]) -> List[Word]:
    """Remove duplicate (english, translation) pairs (case-insensitive)."""
    seen: set = set()
    result = []
    for pair in pairs:
        key = (pair.english.lower(), pair.translation.lower())
        if key not in seen:
            seen.add(key)
            result.append(pair)
    return result
