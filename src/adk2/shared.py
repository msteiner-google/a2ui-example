"""Shared resources for the adk2 package."""

import os

from google import genai
from google.adk.models.google_llm import Gemini

client_global = genai.Client(
    # api_key=os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
    vertexai=True,
    location="global",
)

global_model = Gemini(
    model="gemini-3-flash-preview",
)
global_model.api_client = client_global
