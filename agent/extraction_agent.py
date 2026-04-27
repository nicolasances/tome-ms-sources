
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from totoms import TotoLogger

from agent.util import _create_llm
from config.config import MyConfig


class Word(BaseModel):
    english: str
    translation: str
    
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
            You are an expert English to Danish translator and you are great at looking at a text and extracting all the words that are in Danish, along with their English translation.
            
            Your task is to read a text and extract Danish words and provide their English translation.
            
            Important rules to follow: 
            1.  Only extract words that are in Danish, not in English.
            
            2.  Do not extract sentences nor short phrases. Only individual words, one at a time. This is important. No more than one word at a time. 
            
            3.  Skip prepositions and very common words like "at", "til", "og", "i", "er", "en", "det", "som", "på", "med", "for", "de", "der", etc. 
                I.e. skip very common words that are not useful to learn on their own.
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