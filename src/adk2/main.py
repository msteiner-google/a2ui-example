"""Main."""

import os
import sys
from typing import Never

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard
from loguru import logger

from adk2.agent_executor import A2UIExampleAgentExecutor


def serve() -> Never:
    """Start the server."""
    try:
        host = os.environ.get("HOST", "0.0.0.0")  # noqa: S104
        port = int(os.environ.get("PORT", "8080"))
        cloud_run_url = os.environ.get("CLOUD_RUN_URL", None)

        agent_url: str = (
            f"http://localhost:{port}/" if cloud_run_url is None else cloud_run_url
        )

        agent_card = AgentCard(
            name="A2UI example agent.",
            description="Demonstrates A2UI capabilities.",
            url=agent_url,
            version="0.0.1",
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
            skills=[],
            capabilities=AgentCapabilities(
                streaming=False,
            ),
        )

        logger.debug("Agent card: {}", agent_card)

        agent_executor = A2UIExampleAgentExecutor(agent_card=agent_card)

        request_handler = DefaultRequestHandler(
            agent_executor=agent_executor,
            task_store=InMemoryTaskStore(),
        )

        a2a_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )
        app = a2a_app.build()

        logger.info("Running server on {}:{}", host, port)
        uvicorn.run(app, host=host, port=port)
    except Exception as e:  # noqa: BLE001
        logger.error("An error occurred during server startup: {}", e)
        sys.exit(1)


if __name__ == "__main__":
    serve()
