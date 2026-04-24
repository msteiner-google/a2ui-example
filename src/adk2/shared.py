"""Shared resources for the adk2 package."""

from google import genai
from google.adk.models.google_llm import Gemini

client_global = genai.Client(
    vertexai=True,
    location="global",
)

global_model = Gemini(
    model="gemini-3-flash-preview",
)
global_model.api_client = client_global
