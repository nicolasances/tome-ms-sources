from typing import Literal

# Prompt for vocabulary extraction — stored here to allow tuning without code changes
EXTRACTION_PROMPT: str = """
    You are a language learning assistant.
    Read the following text and extract every word or short phrase that is written in the target language
    (not in English), along with its English meaning.
    Return a JSON object with a single key 'words' whose value is a list of objects,
    each having 'english' (the English meaning) and 'translation' (the target-language word or phrase).
    Only include entries where both fields are non-empty strings.
    Do not include any other text outside the JSON object.

    Text:
    {text}
"""


def get_prompt(type: Literal["extraction"] = "extraction") -> str:
    """Return the prompt template for the given type."""
    if type == "extraction":
        return EXTRACTION_PROMPT
    else:
        raise ValueError(f"Unsupported prompt type: {type}")