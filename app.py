"""
Toto Tome Scraper - Microservice for scraping and processing tome content.

Uses TotoMicroservice framework for:
- Configuration management
- API controller with FastAPI
- Message bus for event handling

Run with: python app.py
"""
import asyncio
import os
from config.config import MyConfig
from totoms import ( TotoMicroservice, TotoMicroserviceConfiguration, TotoEnvironment, APIConfiguration, )
from totoms.TotoMicroservice import APIEndpoint, determine_environment

from dlg.hello import say_hello

def get_microservice_config() -> TotoMicroserviceConfiguration:
    """Create and return the microservice configuration."""
    return TotoMicroserviceConfiguration(
        service_name="tome-ms-sources",
        base_path="/tomesources",
        environment=TotoEnvironment(
            hyperscaler=os.getenv("HYPERSCALER", "aws").lower(),
            hyperscaler_configuration=determine_environment()
        ),
        custom_config=MyConfig,
        api_configuration=APIConfiguration(
            api_endpoints=[
                APIEndpoint(method="GET", path="/hello", delegate=say_hello),
            ]
        ),
    )


async def main():
    """Main entry point for running the microservice."""
    microservice = await TotoMicroservice.init(get_microservice_config())
    port = int(os.getenv("PORT", "8080"))
    await microservice.start(port=port)


if __name__ == "__main__":
    asyncio.run(main())
