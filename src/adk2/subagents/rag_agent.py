"""Simulate the rag agent."""

from __future__ import annotations

import json
import textwrap
import uuid
from pathlib import Path

import jinja2
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext  # noqa: TC002
from google.adk.agents.context import Context  # noqa: TC002
from google.adk.models import LlmRequest, LlmResponse
from google.adk.tools import FunctionTool
from google.adk.workflow import Workflow
from google.genai.types import Content, GenerateContentConfig, Part
from loguru import logger
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
_SEARCH_THRESHOLD = 60.0


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
        limit=None,
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
    return MockExtractedQuery.model_validate_json(response.text)


def _maybe_reply_text_or_a2ui_json(node_input: list[MockSearchResult]) -> str:
    """Formats results as A2UI JSON if many, otherwise as a simple list."""
    if len(node_input) > _MAX_RESULTS_WITHOUT_UI:
        # Load and render template
        template = template_env.get_template("show_dropdown.json.j2")
        surface_id = f"traiff-selection-surface-{uuid.uuid4().hex[:8]}"
        rendered_json = template.render(items=node_input, surface_id=surface_id)

        # Create a new content object with the a2ui-json block
        a2ui_block = f"\n\n<a2ui-json>\n{rendered_json}\n</a2ui-json>"
        intro_text = textwrap.dedent("""\
        I found multiple policies. Please select one from the list below or use the
        filter to narrow down your search.
        """)
        return intro_text + a2ui_block

    # Return a simple text list for the LLM to format nicely
    lines = [f"- {res.document_id}: {res.document_body}" for res in node_input]
    return "\n".join(lines)


_search_db_workflow = Workflow(
    name="search_db_workflow",
    description="Searches the policies db and formats the response.",
    nodes=[
        _extract_query_function,
        _mock_search_db_function,
        _maybe_reply_text_or_a2ui_json,
    ],
    edges=[
        ("START", _extract_query_function),
        (_extract_query_function, _mock_search_db_function),
        (_mock_search_db_function, _maybe_reply_text_or_a2ui_json),
    ],
)


async def _run_search_db_workflow(user_input: str, ctx: Context) -> str:
    """Invokes the search db workflow."""
    return await ctx.run_node(
        node=_search_db_workflow,
        node_input=Content(parts=[Part(text=user_input)]),
    )


_workflow_tool = FunctionTool(
    func=_run_search_db_workflow,
)


def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> LlmResponse | None:
    """Consolidated gatekeeper: forces tools and injects UI, skipping LLM."""
    logger.info("--- before_model_callback ---")

    if not llm_request.contents:
        return None

    # 1. Check if the last event contains <a2ui-json> (SUMMARIZATION PHASE)
    if callback_context.session.events:
        last_event = callback_context.session.events[-1]

        # Extract text from the event
        full_text = ""
        if last_event.content and last_event.content.parts:
            for p in last_event.content.parts:
                if p.text:
                    full_text += p.text
                elif p.function_response and p.function_response.response:
                    res = p.function_response.response
                    if isinstance(res, dict) and "result" in res:
                        full_text += str(res["result"])
                    else:
                        full_text += str(res)

        if "<a2ui-json>" in full_text:
            logger.info("Detected <a2ui-json> in last event. Skipping LLM.")
            return LlmResponse(
                content=Content(role="model", parts=[Part(text=full_text)])
            )

    return None


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
    before_model_callback=before_model_callback,
    mode="chat",
)
