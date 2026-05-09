from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from totoms import TotoLogger

from agent.util import _create_llm
from config.config import MyConfig


class GeneratedSentence(BaseModel):
    sentence: str
    translation: str

class GeneratedSentences(BaseModel):
    sentences: List[GeneratedSentence]


class SentenceGenerationAgent:
    """Generates one Danish sentence per seed word."""

    def __init__(self, config: MyConfig):
        self.config = config
        self.hyperscaler = config.environment.hyperscaler

    async def generate(self, seed_words: List[str]) -> GeneratedSentences:
        """
        Generate one sentence per seed word.

        Each sentence must naturally use its assigned seed word (or a
        grammatically appropriate inflected form of it). Sentences must be
        realistic, meaningful Danish — not artificial constructions that force
        unrelated vocabulary together.
        """
        logger = TotoLogger.get_instance()
        llm = _create_llm(self.hyperscaler)

        word_list = "\n".join(f"- {w}" for w in seed_words)

        prompt = """
            You are an expert Danish language teacher creating example sentences for language learners.

            You will receive a list of Danish vocabulary words (or English words with their Danish equivalent).
            For each word, generate exactly ONE natural Danish sentence that uses that word.

            Rules:
            1. Generate exactly one sentence per word — the same number of sentences as words provided.
            2. Each sentence must contain the assigned seed word or a grammatically appropriate inflected/conjugated form of it.
               For example, the word "at lave" (to make/do) may appear as "laver", "lavede", "lavet", "lav", etc.
            3. Each sentence must be realistic and meaningful — something a native Danish speaker would genuinely say in everyday life.
            4. Do NOT force multiple unrelated vocabulary words into the same sentence. If additional seed words happen to
               fit naturally, that is fine, but it must never be the primary goal.
            5. Each sentence must be a complete sentence (subject + verb), not a fragment or an isolated word.
            6. Provide an accurate English translation for each sentence.

            Return a JSON object with a single key 'sentences' whose value is a list of objects,
            each having 'sentence' (the Danish sentence) and 'translation' (the English translation).
            The list must have exactly as many entries as there are seed words.

            Do not include any text outside the JSON object.
        """

        structured_llm = llm.with_structured_output(GeneratedSentences)
        logger.log("", f"Generating sentences for {len(seed_words)} seed words")

        result: GeneratedSentences = await structured_llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Generate one Danish sentence for each of the following words:\n\n{word_list}"),
        ])  # type: ignore

        logger.log("", f"Generated {len(result.sentences)} sentences")
        return result
