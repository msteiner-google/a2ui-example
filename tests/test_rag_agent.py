"""Tests for the rag_agent subagent."""

import pytest

from adk2.models.rag_model import MockExtractedQuery, MockSearchResult
from adk2.subagents.rag_agent import (
    _SEARCH_THRESHOLD,  # noqa: PLC2701
    _mock_db,  # noqa: PLC2701
    _mock_search_db_function,  # noqa: PLC2701
)

FULL_MATCH_SCORE = 100.0


def test_mock_search_db_function_returns_results() -> None:
    """Test that the search function returns a list of MockSearchResult."""
    results = _mock_search_db_function(
        node_input=MockExtractedQuery(query="vacation")
    )
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(res, MockSearchResult) for res in results)


def test_mock_search_db_function_empty_query() -> None:
    """Test that an empty query returns all results."""
    results = _mock_search_db_function(node_input=MockExtractedQuery(query=""))
    assert len(results) == len(_mock_db)
    assert all(res.score == pytest.approx(FULL_MATCH_SCORE) for res in results)


def test_mock_search_db_function_threshold() -> None:
    """Test that the search function respects the threshold."""
    # We use a query that likely has many mid-score matches
    results = _mock_search_db_function(node_input=MockExtractedQuery(query="policy"))
    # If there are results above threshold, they should all be >= threshold
    # Given the mock data, "policy" should have matches.
    # Let's verify that IF we have results, they are either all above threshold
    # OR it's the full set of results.
    if any(res.score >= _SEARCH_THRESHOLD for res in results) and len(results) < len(
        _mock_db
    ):
        assert all(res.score >= _SEARCH_THRESHOLD for res in results)


def test_mock_search_db_function_fallback() -> None:
    """Test that if no match is above threshold, all results are returned."""
    # Using a very unlikely string that should result in low scores
    results = _mock_search_db_function(
        node_input=MockExtractedQuery(query="%%%$$$###@@@!!!")
    )
    assert len(results) == len(_mock_db)
    # Check that they are still sorted
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score


def test_mock_search_db_function_score_sorting() -> None:
    """Test that results are sorted by score (higher is better)."""
    results = _mock_search_db_function(node_input=MockExtractedQuery(query="insurance"))
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score


def test_mock_search_db_function_content() -> None:
    """Test that results contain the expected fields."""
    results = _mock_search_db_function(node_input=MockExtractedQuery(query="vacation"))
    if results:
        res = results[0]
        assert res.document_id is not None
        assert res.document_body is not None
        assert isinstance(res.score, float)
