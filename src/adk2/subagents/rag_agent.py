"""Simulate the rag agent."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import jinja2
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext  # noqa: TC002
from google.adk.agents.context import Context  # noqa: TC002
from google.adk.tools import FunctionTool
from google.adk.workflow import Workflow
from google.genai.types import Content, GenerateContentConfig, Part
from rapidfuzz import fuzz, process

from adk2.models.rag_model import MockExtractedQuery, MockSearchResult
from adk2.shared import client_global, global_model

# Initialize Jinja2 environment
template_loader = jinja2.FileSystemLoader(searchpath="data")
template_env = jinja2.Environment(loader=template_loader, autoescape=True)

_MAX_RESULTS_WITHOUT_UI = 5


def _load_mock_db() -> list[tuple[str, str]]:
    """Loads the mock database from a JSON file."""
    # Look for the file in the project root's data folder.
    # We try both relative to the current working directory and relative to this file.
    possible_paths = [
        Path("data/mock_policies.json"),
        Path(__file__).resolve().parents[3] / "data" / "mock_policies.json",
    ]

    for data_path in possible_paths:
        if data_path.exists():
            with data_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return [(item["id"], item["description"]) for item in data]

    raise FileNotFoundError(  # noqa: TRY003
        f"Could not find data/mock_policies.json in: {[str(p) for p in possible_paths]}"
    )


_mock_db: list[tuple[str, str]] = _load_mock_db()
_SEARCH_THRESHOLD = 30.0


def _mock_search_db_function(
    node_input: MockExtractedQuery,
) -> list[MockSearchResult]:
    """Searches the mock database for the more suitable policies."""
    choices = dict(_mock_db)

    if not node_input.query.strip() or node_input.query.lower() == "all":
        return [
            MockSearchResult(
                document_id=str(id_),
                document_body=desc,
                score=100.0,
            )
            for id_, desc in _mock_db
        ]

    results = process.extract(
        node_input.query,
        choices.keys(),
        scorer=fuzz.WRatio,
        score_cutoff=_SEARCH_THRESHOLD,
    )

    if not results:
        results = process.extract(
            node_input.query,
            choices.keys(),
            scorer=fuzz.WRatio,
            limit=None,
        )

    return [
        MockSearchResult(
            document_id=str(id_),
            document_body=choices[str(id_)],
            score=float(score),
        )
        for id_, score, _ in results
    ]


async def _extract_query_function(
    node_input: Content,
) -> MockExtractedQuery:
    """Extracts the query from the user input."""
    user_input = "".join([p.text for p in node_input.parts if p.text])
    # Use the client directly to avoid ADK model path issues
    prompt = (
        f"Extract the insurance policy query from the user input: {user_input}. "
        "If they want to see all policies, use an empty string or 'all'. "
        "Return ONLY a JSON object with a single 'query' key."
    )
    response = await client_global.aio.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[prompt],
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MockExtractedQuery,
        ),
    )
    # The response.text should be a JSON string matching MockExtractedQuery
    return MockExtractedQuery.model_validate_json(response.text)


_search_db_workflow = Workflow(
    name="search_db_workflow",
    description="Searches the policies db.",
    nodes=[_extract_query_function, _mock_search_db_function],
    edges=[
        ("START", _extract_query_function),
        (_extract_query_function, _mock_search_db_function),
    ],
)


async def _run_search_db_workflow(
    user_input: str, ctx: Context
) -> list[MockSearchResult]:
    """Invokes the search db workflow."""
    return await ctx.run_node(
        node=_search_db_workflow,
        node_input=Content(parts=[Part(text=user_input)]),
    )


_workflow_tool = FunctionTool(
    func=_run_search_db_workflow,
)


def _find_search_results(session_events: list) -> list[MockSearchResult]:
    """Finds search results in session events."""
    for event in reversed(session_events):
        # Check event.output first (ADK standard for node results)
        output = getattr(event, "output", None)
        if output and isinstance(output, list) and output:
            if all(isinstance(i, MockSearchResult) for i in output):
                return output
            if all(isinstance(i, dict) and "document_id" in i for i in output):
                return [MockSearchResult(**i) for i in output]

        # Fallback to checking content parts if they exist
        if (
            hasattr(event, "content")
            and event.content
            and hasattr(event.content, "parts")
            and event.content.parts
        ):
            for part in event.content.parts:
                data = getattr(part, "data", None)
                if data and isinstance(data, list) and data:
                    if all(isinstance(i, MockSearchResult) for i in data):
                        return data
                    if all(isinstance(i, dict) and "document_id" in i for i in data):
                        return [MockSearchResult(**i) for i in data]
    return []


def attach_a2ui_json_callback(callback_context: CallbackContext) -> Content | None:
    """Attaches A2UI JSON if more than 5 search results are returned."""
    search_results = _find_search_results(callback_context.session.events)

    if len(search_results) <= _MAX_RESULTS_WITHOUT_UI:
        return None

    # Load and render template
    template = template_env.get_template("show_dropdown.json.j2")
    rendered_json = template.render(items=search_results)

    # Get the agent's original output (the last event in the session)
    # If the session is empty or doesn't have content, return None
    if not callback_context.session.events:
        return None

    original_content = callback_context.session.events[-1].content
    if not original_content:
        return None

    # Create a new content object with the a2ui-json block appended
    a2ui_block = f"\n\n<a2ui-json>\n{rendered_json}\n</a2ui-json>"

    # Check if the block is already present to avoid infinite loops or double injection
    full_text = "".join([p.text for p in original_content.parts if p.text])
    if "<a2ui-json>" in full_text:
        return None

    # Replace the text with a brief introduction instead of keeping the long list
    intro_text = "I found multiple policies. Please select one from the list below or use the filter to narrow down your search."
    new_parts = [Part(text=intro_text + a2ui_block)]

    return Content(role="model", parts=new_parts)


rag_agent = LlmAgent(
    name="rag_agent",
    model=global_model,
    description=textwrap.dedent(
        """\
        Search across the database for the more suitable policies.
        Can ask clarifying questions and show UI elements.
        """,
    ),
    tools=[_workflow_tool],
    after_agent_callback=[attach_a2ui_json_callback],
    mode="chat",
)
