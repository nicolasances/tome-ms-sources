
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from totoms import TotoLogger

from agent.util import _create_llm
from config.config import MyConfig


class Word(BaseModel):
    english: str
    translation: str
    knowledgeSource: str = ""
    
class Words(BaseModel): 
    words: List[Word]

class KnowledgeExtractionAgent: 
    
    def __init__(self, config: MyConfig):
        self.config = config
        self.hyperscaler = config.environment.hyperscaler
        
    async def _extract_knowledge_from_chunk(self, chunk: str) -> Words:
        """Extract knowledge from a text chunk using the configured prompt."""
        
        logger = TotoLogger.get_instance()
        
        # 1. Create the llm 
        llm = _create_llm(self.hyperscaler)
        
        # 2. Create the prompt
        prompt = f"""
            You are an expert English to Danish translator building a vocabulary list for language learners.

            Your task is to extract Danish vocabulary from a text that will be used for translation quizzes 
            (e.g., "Translate 'to live' to Danish" → "at bo").

            Important rules:

            1. WORD FORMS - Always use dictionary/base forms:
               - Verbs: Use infinitive with "at" prefix (e.g., "at bo", "at lære", "at kæmpe")
               - Nouns: Use indefinite singular with article (e.g., "en ven", "et liv", "en hemmelighed")
               - Adjectives: Use base form (e.g., "modig" not "modige")

            2. ENGLISH SIDE - Match the Danish form:
               - For verbs: use "to + verb" (e.g., "to live", "to learn")
               - For nouns: use "a/an + noun" or just the noun (e.g., "a friend", "life")

            3. IDIOMATIC EXPRESSIONS - Keep meaningful phrases together:
               - If words only make sense together, extract as a phrase (e.g., "makes sense" → "giver mening", "to need" → "at have brug for")
               - Don't break idioms into individual words

            4. SKIP these:
               - Very common words (at, til, og, i, er, en, det, som, på, med, for, de, der)
               - Words that are identical in English and Danish
               - Words that don't make sense as standalone quiz items
               - Duplicate word forms (if you already have "a friend/en ven", don't add "friends/venner")

            5. QUIZ SUITABILITY - Only extract words where:
               - The English prompt clearly indicates what translation is expected
               - The translation is unambiguous enough for a quiz
        """
        
        # 3. Create a structured output chain
        structured_llm = llm.with_structured_output(Words)

        logger.log("", f"Created structured LLM with hyperscaler: {self.hyperscaler}")

        # 4. Invoke the chain and get a Words instance directly
        words: Words = await structured_llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Extract the Danish words and their English translation from the following text: " + chunk),
        ])

        logger.log("", f"Extracted {len(words.words)} words")
        logger.log("", f"First extracted words: {words.words[:20]}")        

        return words