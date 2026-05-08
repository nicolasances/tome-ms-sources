from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from totoms import TotoLogger

from agent.util import _create_llm
from config.config import MyConfig

# Minimum number of words a sentence must have to be kept.
# This is a backstop filter applied after the LLM responds.
MIN_SENTENCE_WORD_COUNT = 4


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

            Read the following text and extract complete Danish sentences that a language learner could use as example sentences.

            STRICT RULES — violating any rule means the entry must be excluded:
            1. Only extract text that is ALREADY PRESENT in the source. Do NOT invent or synthesise anything.
            2. A valid entry MUST be a grammatically complete sentence: it must have at least a subject and a conjugated verb.
               Isolated words, noun phrases, adjectives, infinitive phrases, and sentence fragments are NEVER valid — exclude them.
               Examples of INVALID entries (do NOT include these):
                 - "En ø"  (noun phrase, no verb)
                 - "øde"  (single adjective)
                 - "Behagelig"  (single adjective)
                 - "En oplevelse"  (noun phrase, no verb)
                 - "Erfaring"  (single noun)
               Examples of VALID entries (these are fine):
                 - "Da jeg var barn, boede jeg i Milano."
                 - "Du er strandet på en øde ø i et helt år."
                 - "Jeg kan godt lide at læse."
            3. A sentence must contain at least 4 words.
            4. If an English translation is already given in the text alongside the Danish sentence, use that translation.
               Otherwise, generate an accurate English translation.
            5. Exclude any entry where the 'sentence' field is entirely in English.
            6. Both 'sentence' and 'translation' must be non-empty strings.

            Return a JSON object with a single key 'sentences' whose value is a list of objects,
            each having 'sentence' (the Danish sentence) and 'translation' (the English translation).

            Do not include any text outside the JSON object.
            If no valid sentences are found, return {"sentences": []}.
        """

        structured_llm = llm.with_structured_output(SentencePairs)
        logger.log("", f"Extracting sentences from chunk (first 300 chars): {chunk[:300]!r}")

        result: SentencePairs = await structured_llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Extract complete Danish sentences from the following text:\n\n" + chunk),
        ])  # type: ignore

        # Backstop: drop anything that doesn't meet the minimum word count
        filtered = [
            s for s in result.sentences
            if len(s.sentence.split()) >= MIN_SENTENCE_WORD_COUNT
        ]

        if len(filtered) < len(result.sentences):
            logger.log("", f"Filtered out {len(result.sentences) - len(filtered)} short entries (< {MIN_SENTENCE_WORD_COUNT} words)")

        logger.log("", f"Extracted {len(filtered)} sentences from chunk")
        return SentencePairs(sentences=filtered)
