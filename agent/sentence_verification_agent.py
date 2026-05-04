from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from totoms import TotoLogger

from agent.util import _create_llm
from agent.sentence_generation_agent import GeneratedSentence
from config.config import MyConfig


class VerifiedSentences(BaseModel):
    sentences: List[GeneratedSentence]


class SentenceVerificationAgent:
    """
    Acts as a Danish language expert. Reviews generated sentences and returns
    only those it considers grammatically correct and natural Danish.
    The agent accepts or rejects each sentence as-is — it never rewrites.
    """

    def __init__(self, config: MyConfig):
        self.config = config
        self.hyperscaler = config.environment.hyperscaler

    async def verify(self, sentences: List[GeneratedSentence]) -> VerifiedSentences:
        """
        Return only the sentences that pass the Danish language quality check.
        Rejected sentences are simply omitted from the output.
        """
        logger = TotoLogger.get_instance()
        llm = _create_llm(self.hyperscaler)

        sentences_text = "\n".join(
            f"{i + 1}. {s.sentence} / {s.translation}"
            for i, s in enumerate(sentences)
        )

        prompt = """
            You are an expert Danish language teacher and native speaker.

            You will receive a list of Danish sentences, each paired with an English translation.
            Your task is to review each sentence and decide whether it is:
            - Grammatically correct Danish
            - Natural and idiomatic (something a native speaker would actually say)
            - Meaningful in a real-life context

            For each sentence that passes all three criteria, include it in your output as-is (do NOT rewrite it).
            Simply omit any sentence that fails even one criterion.

            Return a JSON object with a single key 'sentences' whose value is a list of objects,
            each having 'sentence' (the original Danish sentence) and 'translation' (the original English translation).

            Do not include any text outside the JSON object.
        """

        structured_llm = llm.with_structured_output(VerifiedSentences)
        logger.log("", f"Verifying {len(sentences)} sentences")

        result: VerifiedSentences = await structured_llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Review the following Danish sentences and return only the correct ones:\n\n{sentences_text}"),
        ])  # type: ignore

        logger.log("", f"Verification passed {len(result.sentences)}/{len(sentences)} sentences")
        return result
