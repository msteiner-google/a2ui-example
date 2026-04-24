"""Root agent."""

import textwrap

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import LlmAgent

from adk2.shared import global_model
from adk2.subagents.rag_agent import rag_agent

# Initialize A2UI Schema Manager
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config(version="0.8")],
    schema_modifiers=[remove_strict_validation],
)


root_agent = LlmAgent(
    name="ui_demo_assistant",
    model=global_model,
    instruction=textwrap.dedent("""\
        You are an internal assistant for a insurance company employees. Answer their
        questions with the tools at your disposal or by delegating the actions
        to the appropriate sub-agent.
    """),
    sub_agents=[rag_agent],
)
