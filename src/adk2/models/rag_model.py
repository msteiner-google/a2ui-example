"""Rag model."""

from pydantic import BaseModel, Field


class MockExtractedQuery(BaseModel):
    """A query against the Policies db."""

    query: str = Field(description="The actual query string.")


class MockSearchResult(BaseModel):
    """The results of a search."""

    document_id: str = Field(description="The id of the document retrieved.")
    document_body: str = Field(description="The actual body of the document.")
    score: float = Field(description="The score of the match. Higher is better.")
