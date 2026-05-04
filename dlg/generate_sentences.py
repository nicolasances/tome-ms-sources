import logging
from typing import List

from fastapi import Request
from fastapi.responses import JSONResponse
from totoms.TotoLogger import TotoLogger
from totoms.TotoDelegateDecorator import toto_delegate
from totoms.model import ExecutionContext, UserContext

from agent.sentence_generation_agent import SentenceGenerationAgent, GeneratedSentence
from agent.sentence_verification_agent import SentenceVerificationAgent
from api.tome_language_api import post_sentences, sample_words
from config.config import MyConfig


@toto_delegate
async def generate_sentences(request: Request, user_context: UserContext, exec_context: ExecutionContext):
    """
    POST /sentences/generate

    Body: { "language": "danish", "count": 10 }

    Samples `count` vocabulary words from tome-ms-language, generates one sentence per
    word (using the LLM), verifies grammar/naturalness, and persists accepted sentences.
    Rejected sentences trigger a resample+regenerate loop up to MAX_GENERATION_ITERATIONS.

    Returns: { language, sentencesGenerated, sentencesCreated, sentencesErrored }
    """
    config: MyConfig = exec_context.config  # type: ignore
    logger = TotoLogger.get_instance()

    body = await request.json()
    language: str = body.get("language", "")
    count: int = body.get("count", 0)

    # ── Validate ──────────────────────────────────────────────────────────────
    if language not in config.supported_languages:
        return JSONResponse(
            content={"message": f"Unsupported language '{language}'. Supported: {config.supported_languages}"},
            status_code=400,
        )
    if not isinstance(count, int) or not (1 <= count <= 50):
        return JSONResponse(
            content={"message": "count must be an integer between 1 and 50"},
            status_code=400,
        )

    auth_header = request.headers.get("Authorization", "")
    correlation_id = exec_context.cid

    # ── Step 1: Sample seed words ─────────────────────────────────────────────
    try:
        seed_words = await _sample_words_async(config, language, count, auth_header, correlation_id)
    except Exception as exc:
        logger.log(correlation_id, f"Failed to sample words: {exc}")
        return JSONResponse(content={"message": "Failed to sample seed words"}, status_code=502)

    if not seed_words:
        return JSONResponse(
            content={
                "language": language,
                "sentencesGenerated": 0,
                "sentencesCreated": 0,
                "sentencesErrored": 0,
            },
            status_code=200,
        )

    generation_agent = SentenceGenerationAgent(config)
    verification_agent = SentenceVerificationAgent(config)

    accepted: List[GeneratedSentence] = []
    pending_words = seed_words  # words still needing a valid sentence

    # ── Steps 2+3: Generate → Verify loop ─────────────────────────────────────
    for iteration in range(config.max_generation_iterations):
        if not pending_words:
            break

        logger.log(correlation_id, f"Generation iteration {iteration + 1}/{config.max_generation_iterations} for {len(pending_words)} words")

        # Generate one sentence per pending seed word
        try:
            word_strings = [w.get("english", str(w)) for w in pending_words]
            generated_result = await generation_agent.generate(word_strings)
            generated = generated_result.sentences
        except Exception as exc:
            logger.log(correlation_id, f"Generation failed on iteration {iteration + 1}: {exc}")
            break

        if not generated:
            break

        # Verify — keep only the accepted ones
        try:
            verified_result = await verification_agent.verify(generated)
            newly_accepted = verified_result.sentences
        except Exception as exc:
            logger.log(correlation_id, f"Verification failed on iteration {iteration + 1}: {exc}")
            break

        accepted.extend(newly_accepted)

        # Determine how many were rejected (approximation: generated − accepted this round)
        rejected_count = len(generated) - len(newly_accepted)
        logger.log(correlation_id, f"Iteration {iteration + 1}: {len(newly_accepted)} accepted, {rejected_count} rejected")

        if rejected_count == 0 or iteration == config.max_generation_iterations - 1:
            break

        # Resample for the rejected sentences
        try:
            pending_words = await _sample_words_async(config, language, rejected_count, auth_header, correlation_id)
        except Exception as exc:
            logger.log(correlation_id, f"Resample failed: {exc}")
            break

    logger.log(correlation_id, f"Total accepted sentences: {len(accepted)}")

    # ── Step 4: POST accepted sentences to tome-ms-language ───────────────────
    sentences_created = 0
    sentences_errored = 0

    if accepted:
        sentence_dicts = [{"sentence": s.sentence, "translation": s.translation} for s in accepted]
        try:
            sentences_created, sentences_errored = post_sentences(
                config, language, sentence_dicts, "tome-agent", auth_header, correlation_id
            )
        except Exception as exc:
            logger.log(correlation_id, f"Failed to post sentences: {exc}")
            sentences_errored = len(accepted)

    return JSONResponse(
        content={
            "language": language,
            "sentencesGenerated": len(accepted),
            "sentencesCreated": sentences_created,
            "sentencesErrored": sentences_errored,
        },
        status_code=200,
    )


async def _sample_words_async(config, language, n, auth_header, correlation_id) -> list:
    """Thin async wrapper — sample_words is sync (requests)."""
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: sample_words(config, language, n, auth_header, correlation_id)
    )
