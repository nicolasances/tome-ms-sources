"""
Utility module for extracting sentences (sentence-translation pairs) from text chunks using LLM.
"""
import logging
from typing import List, Tuple

from agent.sentence_extraction_agent import SentenceExtractionAgent, SentencePair
from agent.sentence_verification_agent import SentenceVerificationAgent
from totoms.TotoLogger import TotoLogger


async def extract_sentences(
    chunks: List[str], language: str, config
) -> Tuple[List[SentencePair], bool]:
    """
    Extract and deduplicate sentence pairs from all chunks via LLM.

    Returns:
        (deduped_sentences, all_failed) — all_failed is True only when every
        chunk failed after its retry.
    """
    agent = SentenceExtractionAgent(config)
    all_pairs: List[SentencePair] = []
    failed_count = 0

    for chunk in chunks:
        try:
            result = await agent.extract(chunk)
            all_pairs.extend(result.sentences)
        except Exception as exc:
            logging.warning("Sentence extraction failed for chunk: %s", exc)
            failed_count += 1

    all_failed = failed_count == len(chunks) and len(chunks) > 0
    return _deduplicate(all_pairs), all_failed


async def verify_sentences(
    sentences: List[SentencePair], config, correlation_id: str = ""
) -> List[SentencePair]:
    """
    Run sentence verification to drop mixed-language or incorrect sentences.
    Returns the verified subset; on failure returns the original list (non-fatal).
    """
    logger = TotoLogger.get_instance()
    if not sentences:
        return sentences
    try:
        agent = SentenceVerificationAgent(config)
        verified = await agent.verify_extracted(sentences)
        logger.log(correlation_id, f"{len(verified)} sentences passed verification")
        return verified
    except Exception as exc:
        logger.log(
            correlation_id,
            f"Sentence verification failed (non-fatal, keeping unverified): {exc}",
        )
        return sentences


def _deduplicate(pairs: List[SentencePair]) -> List[SentencePair]:
    """Remove duplicate sentences (case-insensitive on the sentence field)."""
    seen: set = set()
    result = []
    for pair in pairs:
        key = pair.sentence.lower()
        if key not in seen:
            seen.add(key)
            result.append(pair)
    return result
