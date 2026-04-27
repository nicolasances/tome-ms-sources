
    
import os

from langchain_aws import ChatBedrock
from langchain_aws.utils import thinking_in_params
from langchain_google_genai import ChatGoogleGenerativeAI
from totoms import TotoLogger


def _create_llm(hyperscaler: str):
    """Create the appropriate LLM based on the hyperscaler."""
    logger = TotoLogger.get_instance()
    provider = hyperscaler.lower()

    if provider == "gcp":
        project = os.environ.get("GCP_PID")
        location = os.environ.get("GCP_REGION", "europe-west1")
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        
        logger.log("INIT", f"Creating Google Gemini LLM with model: {model}, project: {project}, location: {location}")
        
        return ChatGoogleGenerativeAI(
            model=model,
            project=project,
            location=location,
            temperature=0,
            thinking_budget=1024,
            include_thoughts=True,
        )

    if provider == "aws":
        model_id = os.environ.get("BEDROCK_MODEL_ID", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0")
        aws_region = os.environ.get("AWS_REGION", "eu-north-1")
        
        logger.log("INIT", f"Creating AWS Bedrock LLM with model: {model_id}, region: {aws_region}")

        return ChatBedrock(
            model_id=model_id,
            region_name=aws_region,
            model_kwargs={
                "thinking": {
                    "type": "enabled",
                    "budget_tokens": 4096,
                },
            },
        )

    raise ValueError(f"Unsupported HYPERSCALER '{hyperscaler}'. Use 'aws' or 'gcp'.")
