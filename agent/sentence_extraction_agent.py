from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from totoms import TotoLogger

from agent.util import _create_llm
from config.config import MyConfig


class SentencePair(BaseModel):
    sentence: str
    translation: str

class SentencePairs(BaseModel):
    sentences: List[SentencePair]


class SentenceExtractionAgent:

    def __init__(self, config: MyConfig):
        self.config = config
        self.hyperscaler = config.environment.hyperscaler

    async def extract(self, chunk: str) -> SentencePairs:
        """Extract sentence-translation pairs from a text chunk."""
        logger = TotoLogger.get_instance()

        llm = _create_llm(self.hyperscaler)

        prompt = """
            You are a language learning assistant specialising in Danish.

            Read the following text and extract every complete sentence or meaningful phrase that is written in Danish.
            For each sentence, provide its English translation.

            Rules:
            1. Only extract sentences that are ALREADY PRESENT in the text. Do NOT invent or synthesise new sentences.
            2. If an English translation is already given in the text alongside the Danish sentence, use that translation.
            3. If no translation is provided in the text, generate an accurate English translation yourself.
            4. A sentence must be a complete phrase — not a single isolated word or a sentence fragment.
            5. Exclude sentences that are entirely in English (only include Danish sentences).
            6. Both 'sentence' and 'translation' must be non-empty strings.

            Return a JSON object with a single key 'sentences' whose value is a list of objects,
            each having 'sentence' (the Danish phrase) and 'translation' (the English translation).

            Do not include any text outside the JSON object.
        """

        structured_llm = llm.with_structured_output(SentencePairs)
        logger.log("", f"Extracting sentences from chunk (first 300 chars): {chunk[:300]!r}")

        result: SentencePairs = await structured_llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Extract Danish sentences and their translations from the following text:\n\n" + chunk),
        ])  # type: ignore

        logger.log("", f"Extracted {len(result.sentences)} sentences from chunk")
        return result
