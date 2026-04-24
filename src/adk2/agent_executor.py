"""A2UI capable executor."""

import uuid
from typing import TYPE_CHECKING, Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCard,
    DataPart,
    Message,
    Part,
    Role,
    TaskState,
    TextPart,
)
from a2a.utils.errors import InternalError
from a2ui.a2a.extension import try_activate_a2ui_extension
from a2ui.a2a.parts import parse_response_to_parts
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from loguru import logger

from adk2.agent import root_agent, schema_manager

if TYPE_CHECKING:
    from a2a.server.events import EventQueue


class A2UIExampleAgentExecutor(AgentExecutor):
    """Insurance Assistant AgentExecutor."""

    def __init__(self, agent_card: AgentCard) -> None:
        """Init method."""
        self._agent_card = agent_card
        self._runner = Runner(
            app_name="ui_demo_assistant_app",
            agent=root_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    async def execute(  # noqa: C901, D102, PLR0912, PLR0914, PLR0915
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = ""
        ui_event_part = None
        action = None

        logger.info(
            "--- Client requested extensions: {} ---", context.requested_extensions
        )
        active_ui_activation = try_activate_a2ui_extension(context, self._agent_card)
        _active_ui_version = active_ui_activation[1] if active_ui_activation else None

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

        task_id = context.task_id
        context_id = context.context_id

        session_id = context_id
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
            # Use validator from schema manager
            validator = schema_manager.get_selected_catalog().validator
            final_parts = parse_response_to_parts(
                final_response_content, validator=validator
            )
            # If no parts were parsed (e.g. no tags found), fallback to text
            if not final_parts:
                final_parts = [Part(root=TextPart(text=final_response_content))]
        except Exception as e:  # noqa: BLE001
            logger.error("Error parsing or validating response to parts: {}", e)
            final_parts = [Part(root=TextPart(text=final_response_content))]

        self._log_parts(final_parts)

        # Determine Task State
        final_state = TaskState.input_required
        if action == "execute_comparison":
            final_state = TaskState.completed

        updater = TaskUpdater(event_queue, task_id, context_id)

        await updater.update_status(
            final_state,
            Message(
                message_id=str(uuid.uuid4()),
                role=Role.agent,
                context_id=context_id,
                task_id=task_id,
                parts=final_parts,
            ),
            final=(final_state == TaskState.completed),
        )

    async def cancel(  # noqa: PLR6301
        self,
        request: RequestContext,  # noqa: ARG002
        event_queue: EventQueue,  # noqa: ARG002
    ) -> Any:  # noqa: ANN401
        """Cancel the requests."""
        raise InternalError(message="Cancel not supported")

    def _unwrap_value(self, val: Any) -> Any:  # noqa: ANN401, PLR6301
        """Unwrap A2UI literal values."""
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

    def _log_parts(self, parts: list[Part]) -> None:  # noqa: PLR6301
        logger.info("--- PARTS TO BE SENT ---")
        for i, part in enumerate(parts):
            logger.info("Part {}: Type = {}", i, type(part.root))
            if isinstance(part.root, TextPart):
                logger.info("Text: {}", part.root.text)
            elif isinstance(part.root, DataPart):
                logger.info("Data: {}", str(part.root.data))
        logger.info("-----------------------------")
