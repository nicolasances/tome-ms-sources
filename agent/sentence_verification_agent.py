from typing import List, Union

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from totoms import TotoLogger

from agent.util import _create_llm
from agent.sentence_generation_agent import GeneratedSentence
from agent.sentence_extraction_agent import SentencePair
from config.config import MyConfig


class VerifiedSentences(BaseModel):
    sentences: List[GeneratedSentence]


_VERIFICATION_PROMPT = """
    You are an expert Danish language teacher and native speaker.

    You will receive a list of sentences, each paired with an English translation.
    Review each sentence and include it in your output ONLY if ALL of the following are true:
    - It is entirely written in Danish — it must not contain words from other languages
      (e.g., English words mixed into an otherwise Danish sentence are grounds for rejection)
    - It is grammatically correct Danish
    - It is natural and idiomatic (something a native speaker would actually say)
    - It is meaningful in a real-life context

    Accept or reject each sentence as-is — do NOT rewrite or correct anything.
    Simply omit any sentence that fails even one criterion.

    Return a JSON object with a single key 'sentences' whose value is a list of objects,
    each having 'sentence' (the original Danish sentence) and 'translation' (the original English translation).

    Do not include any text outside the JSON object.
    If no sentences pass, return {"sentences": []}.
"""


class SentenceVerificationAgent:
    """
    Acts as a Danish language expert. Reviews sentences (extracted or generated)
    and returns only those that are grammatically correct, natural, and purely Danish.
    The agent accepts or rejects each sentence as-is — it never rewrites.
    """

    def __init__(self, config: MyConfig):
        self.config = config
        self.hyperscaler = config.environment.hyperscaler

    async def verify(self, sentences: List[GeneratedSentence]) -> VerifiedSentences:
        """Verify generated sentences. Returns only the accepted ones."""
        return await self._run_verification(sentences)

    async def verify_extracted(self, sentences: List[SentencePair]) -> List[SentencePair]:
        """
        Verify extracted sentences. Returns only the accepted ones as SentencePairs.
        Rejects sentences with grammar errors, non-Danish words, or mixed-language content.
        """
        if not sentences:
            return []

        # Convert to GeneratedSentence for the shared verification logic
        as_generated = [GeneratedSentence(sentence=s.sentence, translation=s.translation) for s in sentences]
        result = await self._run_verification(as_generated)

        # Convert back to SentencePair
        accepted_texts = {s.sentence for s in result.sentences}
        return [s for s in sentences if s.sentence in accepted_texts]

    async def _run_verification(self, sentences: List[GeneratedSentence]) -> VerifiedSentences:
        logger = TotoLogger.get_instance()
        llm = _create_llm(self.hyperscaler)

        sentences_text = "\n".join(
            f"{i + 1}. {s.sentence} / {s.translation}"
            for i, s in enumerate(sentences)
        )

        structured_llm = llm.with_structured_output(VerifiedSentences)
        logger.log("", f"Verifying {len(sentences)} sentences")

        result: VerifiedSentences = await structured_llm.ainvoke([
            SystemMessage(content=_VERIFICATION_PROMPT),
            HumanMessage(content=f"Review the following sentences and return only the correct Danish ones:\n\n{sentences_text}"),
        ])  # type: ignore

        logger.log("", f"Verification passed {len(result.sentences)}/{len(sentences)} sentences")
        return result
