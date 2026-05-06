"""Agent Engine compatible executor."""

import uuid
from typing import TYPE_CHECKING, Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    DataPart,
    Message,
    Part,
    Role,
    TaskState,
    TextPart,
)
from a2a.utils import (
    new_agent_parts_message,
    new_task,
)
from a2a.utils.errors import InternalError
from a2ui.a2a.extension import try_activate_a2ui_extension
from a2ui.a2a.parts import parse_response_to_parts
# from a2ui.core.schema.constants import VERSION_0_8
VERSION_0_8 = "0.8"
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from loguru import logger

from .agent import root_agent, schema_manager

if TYPE_CHECKING:
    from a2a.server.events import EventQueue


class AgentEngineExecutor(AgentExecutor):
    """Insurance Assistant AgentExecutor for Agent Engine."""

    def __init__(self, agent_card: AgentCard | dict) -> None:
        """Init method."""
        if isinstance(agent_card, dict):
            self._agent_card = AgentCard(**agent_card)
        else:
            self._agent_card = agent_card
            
        self._runner = Runner(
            app_name="ui_demo_assistant_app",
            agent=root_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = ""
        ui_event_part = None
        action = None

        logger.info("--- Client requested extensions: {} ---", context.requested_extensions)
        
        # Hardcoded for now as per user snippet to ensure UI flow
        active_ui_version = VERSION_0_8
        
        if active_ui_version:
            logger.info("--- AGENT_EXECUTOR: A2UI extension is active (v{}). ---", active_ui_version)

        if context.message and context.message.parts:
            for i, part in enumerate(context.message.parts):
                if isinstance(part.root, DataPart):
                    if "userAction" in part.root.data:
                        logger.info(" Part {}: Found a2ui UI ClientEvent payload.", i)
                        ui_event_part = part.root.data["userAction"]
                    else:
                        logger.info(f" Part {i}: DataPart (data: {part.root.data})")
                elif isinstance(part.root, TextPart):
                    logger.info(f" Part {i}: TextPart (text: {part.root.text})")

        if ui_event_part:
            logger.info("Received a2ui ClientEvent: {}", ui_event_part)
            action = ui_event_part.get("name") or ui_event_part.get("actionName")
            ctx = ui_event_part.get("context", {})

            # Structured Intent Mapping
            if action == "show_details":
                val = ctx.get("selected_policies")
                selected_policies = self._unwrap_value(val) if val else []
                item_id = selected_policies[0] if selected_policies else "unknown"
                query = f"ACTION: show_details ITEM: {item_id}"
            elif action == "filter_policies":
                val = ctx.get("filter_query")
                filter_query = self._unwrap_value(val) if val else ""
                query = f"ACTION: filter_policies QUERY: {filter_query}"
            elif action == "go_back":
                query = "ACTION: go_back"
            else:
                query = f"USER_SUBMITTED_EVENT: {action} DATA: {ctx}"
        else:
            logger.info("No a2ui UI event part found. Falling back to text input.")
            query = context.get_user_input()

        logger.info("--- AGENT_EXECUTOR: Final query for LLM: '{}' ---", query)

        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        session_id = task.context_id
        session = await self._runner.session_service.get_session(
            app_name="ui_demo_assistant_app",
            user_id="remote_agent",
            session_id=session_id,
        )
        if session is None:
            session = await self._runner.session_service.create_session(
                app_name="ui_demo_assistant_app",
                user_id="remote_agent",
                state={},
                session_id=session_id,
            )

        current_message = types.Content(
            role="user", parts=[types.Part.from_text(text=query)]
        )

        all_model_contents = []
        async for event in self._runner.run_async(
            user_id="remote_agent",
            session_id=session.id,
            new_message=current_message,
        ):
            if event.content and event.content.role == "model" and event.content.parts:
                parts_text = "".join([
                    part.text for part in event.content.parts if part.text
                ])
                if parts_text:
                    all_model_contents.append(parts_text)

        final_response_content = "\n".join(all_model_contents)

        try:
            validator = schema_manager.get_selected_catalog().validator
            final_parts = parse_response_to_parts(
                final_response_content, validator=validator
            )
            if not final_parts:
                final_parts = [Part(root=TextPart(text=final_response_content))]
        except Exception as e:
            logger.error("Error parsing or validating response to parts: {}", e)
            final_parts = [Part(root=TextPart(text=final_response_content))]

        self._log_parts(final_parts)

        await updater.add_artifact(final_parts, name="response")
        await updater.complete()

    async def cancel(
        self,
        request: RequestContext,
        event_queue: EventQueue,
    ) -> Any:
        raise InternalError(message="Cancel not supported")

    def _unwrap_value(self, val: Any) -> Any:
        if isinstance(val, dict):
            if "literalArray" in val:
                return val["literalArray"]
            if "literalString" in val:
                return val["literalString"]
            if "literalNumber" in val:
                return val["literalNumber"]
            if "literalBoolean" in val:
                return val["literalBoolean"]
        return val

    def _log_parts(self, parts: list[Part]) -> None:
        logger.info("--- PARTS TO BE SENT ---")
        for i, part in enumerate(parts):
            logger.info("Part {}: Type = {}", i, type(part.root))
            if isinstance(part.root, TextPart):
                logger.info("Text: {}", part.root.text)
            elif isinstance(part.root, DataPart):
                logger.info("Data: {}", str(part.root.data))
        logger.info("-----------------------------")
